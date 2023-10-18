import time

from bs4 import BeautifulSoup
from google.cloud import storage
from google.oauth2 import service_account
import requests
import json
import os
import modal
from tqdm import tqdm
from dotenv import load_dotenv

load_dotenv()

# definition of our container image for jobs on Modal
# Modal gets really powerful when you start using multiple images!
image = modal.image.Image.debian_slim(  # we start from a lightweight linux distro
    python_version="3.10"  # we add a recent Python version
).pip_install(  # and we install the following packages:
    "google-cloud-storage",
    "requests",
    "python-dotenv",
    "beautifulsoup4",
    "tqdm",
    "ndg-httpsclient"
)

# we define a Stub to hold all the pieces of our app
# most of the rest of this file just adds features onto this Stub
stub = modal.stub.Stub(
    name="mechanic-scraper",
    image=image,
    secrets=[
        # this is where we add API keys, passwords, and URLs, which are stored on Modal
        modal.secret.Secret.from_name("my-googlecloud-secret")
    ]
)

webpages = {
    "edmunds": "https://forums.edmunds.com/discussions/tagged/x/repairs-maintenance/",
}


@stub.function(concurrency_limit=20)
def scrape_forum_table(i):
    data = []
    main_url = webpages['edmunds'] + f'p{i}'
    html_page = requests.get(main_url)
    soup = BeautifulSoup(html_page.text, "html.parser")

    lists = soup.find("ul", attrs={'class': 'DataList Discussions pageBox'})
    lists_elements = lists.find_all("li")
    for li in lists_elements:
        title = li.find("div", attrs={'class': 'Title'})
        link = str(title.find('a')['href'])
        meta = li.find('div', attrs={'class': 'Meta Meta-Discussion'})
        all_spans = meta.find_all('span')
        meta_date = all_spans[-2]

        tag_matches = ['Answered', 'Poll', 'Question', 'Closed']

        if any([x in all_spans[0].text for x in tag_matches]):
            try:
                obj = {
                    'title': title.text,
                    'link': link,
                    'metadata': {
                        'views': all_spans[1].find('span')['title'],
                        'comments': all_spans[3].find('span')['title'],
                        'date': str(meta_date.find('time')['datetime']),
                        'category': all_spans[-1].text,
                        'status': all_spans[0].text,
                        'closed': False
                    }
                }
            except TypeError:
                obj = {
                    'title': title.text,
                    'link': link,
                    'metadata': {
                        'views': all_spans[2].find('span')['title'],
                        'comments': all_spans[4].find('span')['title'],
                        'date': str(meta_date.find('time')['datetime']),
                        'category': all_spans[-1].text,
                        'status': all_spans[0].text,
                        'closed': True
                    }
                }
        else:
            obj = {
                'title': title.text,
                'link': link,
                'metadata': {
                    'views': all_spans[0].find('span')['title'],
                    'comments': all_spans[2].find('span')['title'],
                    'date': str(meta_date.find('time')['datetime']),
                    'category': all_spans[-1].text,
                    'status': 'open',
                    'closed': False
                }
            }
        data.append(obj)
    return data


@stub.function(concurrency_limit=400, timeout=86400)
def scrape_conversation(obj):
    time.sleep(7)
    html_page = requests.get(obj['link'], stream=True)
    soup = BeautifulSoup(html_page.text, "html.parser")

    discussion = None
    class_tags = ['Item ItemDiscussion Role_Member noPhotoWrap pageBox',
                  'Item ItemDiscussion  Role_Member noPhotoWrap pageBox',
                  'Item ItemDiscussion Role_Member Role_Administrator Role_Moderator noPhotoWrap pageBox',
                  'Item ItemDiscussion  Role_Member Role_Moderator noPhotoWrap pageBox',
                  'Item ItemDiscussion  Role_Moderator noPhotoWrap pageBox',
                  'Item ItemDiscussion Role_Moderator noPhotoWrap pageBox',
                  'Item ItemDiscussion  Role_Administrator noPhotoWrap pageBox',
                  'Item ItemDiscussion Role_Administrator noPhotoWrap pageBox',
                  'Item ItemDiscussion noPhotoWrap pageBox',
                  'Item ItemDiscussion Role_Guest noPhotoWrap pageBox',
                  'Item ItemDiscussion  Role_Guest noPhotoWrap pageBox',
                  'Item ItemDiscussion  Role_Member Banned noPhotoWrap pageBox',
                  'Item ItemDiscussion Role_Member Banned noPhotoWrap pageBox',
                  'Item ItemDiscussion  Role_Member noPhotoWrap pageBox',
                  'Item ItemDiscussion  Role_Member Role_Administrator noPhotoWrap pageBox',
                  'Item ItemDiscussion  Role_Member Role_Administrator Role_Moderator noPhotoWrap pageBox']
    for tags in class_tags:
        discussion = soup.find('div', attrs={'class': tags})
        if discussion is not None:
            break

    if discussion is None:
        print(obj['link'])
        return obj

    inline_tags = discussion.find('div', attrs={'class': 'InlineTags Meta'})
    tags_list = inline_tags.find_all('li')

    author_header = discussion.find('div', attrs={'class': 'Item-Header DiscussionHeader'})
    author_body = discussion.find('div', attrs={'class': 'Item-BodyWrap'})

    obj['author'] = author_header.find('span', attrs={'class': 'Author'}).find_all('a')[-1].text
    obj['author_post_count'] = author_header.find('span', attrs={'class': 'AuthorInfo'}).find_all('span')[-1].find(
        'b').text
    obj['author_role_title'] = author_header.find('span', attrs={'class': 'AuthorInfo'}).find_all('span')[0].text

    descr = author_body.find('div', attrs={'class': 'Message userContent'})
    obj['description'] = descr.text
    try:
        obj['image'] = descr.find('img')['src']
    except TypeError:
        obj['image'] = None

    obj['tags'] = [li.text for li in tags_list]

    comments_list = []
    comment_wrap = soup.find('div', attrs={'class': 'CommentsWrap'})

    try:
        comment_nav = comment_wrap.find('span', attrs={'class': 'Pager PagerLinkCount-11 NumberedPager'})
        last_comment_page = comment_nav.find_all('a')[-3].text
    except AttributeError:
        last_comment_page = 1

    for i in range(0, int(last_comment_page)):
        time.sleep(5)
        comment_url = obj['link'] + f'/p{i + 1}'
        comment_page = requests.get(comment_url)
        comment_soup = BeautifulSoup(comment_page.text, "html.parser")

        # Save verified answers
        if 'Answered' in obj['metadata']['status']:
            try:
                answered_comments_ul = comment_soup.find('ul', attrs={
                    'class': 'MessageList DataList AcceptedAnswers pageBox'})
                all_comments = answered_comments_ul.find_all('li')
                li = all_comments[0]
                comment_obj = {
                    'comment_author': li.find('span', attrs={'class': 'Author'}).find_all('a')[-1].text,
                    'comment_author_post_count': li.find('span', attrs={'class': 'AuthorInfo'}).find_all('span')[
                        -1].find('b').text,
                    'comment_author_role_title': li.find('span', attrs={'class': 'AuthorInfo'}).find_all('span')[
                        0].text,
                    'comment_date_created': li.find('span', attrs={'class': 'MItem DateCreated'}).find('time')[
                        'datetime'],
                    'comment_text': li.find('div', attrs={'class': 'Message userContent'}).text,
                }
                comments_list.append(comment_obj)
            except AttributeError as e:
                print(e)

        try:
            comments_ul = comment_soup.find('ul', attrs={'class': 'MessageList DataList Comments pageBox'})
            all_comments = comments_ul.find_all('li')
        except AttributeError:
            all_comments = []

        for li in all_comments:
            try:
                comment_obj = {
                    'comment_author': li.find('span', attrs={'class': 'Author'}).find_all('a')[-1].text,
                    'comment_author_post_count': li.find('span', attrs={'class': 'AuthorInfo'}).find_all('span')[
                        -1].find('b').text,
                    'comment_author_role_title': li.find('span', attrs={'class': 'AuthorInfo'}).find_all('span')[
                        0].text,
                    'comment_date_created': li.find('span', attrs={'class': 'MItem DateCreated'}).find('time')[
                        'datetime'],
                    'comment_text': li.find('div', attrs={'class': 'Message userContent'}).text,
                }
                comments_list.append(comment_obj)
            except AttributeError:
                print(comment_url)
                print(li)

    obj['comments'] = comments_list

    return obj


def scrape_edmumds():
    data = []
    comment_data = []
    ps = list(range(1, 420))

    try:
        print(f"Scraping Edmunds...")
        for result in scrape_forum_table.map(ps):
            data.extend(result)

        print("Scraping Conversations...")
        for result in scrape_conversation.map(data):
            comment_data.append(result)
    except KeyboardInterrupt:
        pass

    print("Saving to GCP...")
    service_account_info = json.loads(os.environ["SERVICE_ACCOUNT_JSON"])
    credentials = service_account.Credentials.from_service_account_info(service_account_info)

    bucket_name = os.environ["GCS_BUCKET_NAME"]
    bucket = storage.Client(credentials=credentials).get_bucket(bucket_name)

    blob = bucket.blob('mechanic-forums/edmunds_forum.json')
    # take the upload outside of the for-loop otherwise you keep overwriting the whole file
    blob.upload_from_string(data=json.dumps(comment_data), content_type='application/json')

    return comment_data


@stub.function(
    image=image,
    timeout=86400,
)
def main():
    print("Starting Scraper...")
    scrape_edmumds()
