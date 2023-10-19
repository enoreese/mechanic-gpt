# mechanic-gpt

Welcome to the GitHub repository for a Mechanic Fine-tuned LLM. 

We use the materials from the
[Edmunds Forum](https://nass.gov.ng/)
as our document corpus,
so the resulting application is great at answering questions about car repairs and maintainance


## Overview

This repository is organized into two parts:

1. **Part 1**: Data Collection and Preprocessing (etl/)
   - This section focuses on the scraping and preprocessing of data from the car epair forums. It covers the steps involved in gathering the necessary data and performing initial data processing tasks.

2. **Part 2**: Fine-tuning (nassbot_app/)
   - This section delves into the essential steps involved in fine-tuning a LLM. 

## Installation

To use the code in this repository, please follow these steps:

1. Clone the repository to your local machine using the following command:
   ```
   git clone https://github.com/enoreese/mechanic-gpt.git
   ```

2. Install the necessary dependencies by running the following command:
   ```
   pip install -r requirements.txt
   ```

3. Once the dependencies are installed, you can explore the code in the respective directories for Part 1 and Part 2.

## Usage

To use the question and answer system and interact with the National Assembly Corpus, follow these steps:

1. Set up the necessary configuration parameters in the `.env` file. Make sure to specify the appropriate paths, endpoints, and credentials required for the system. If you haven't already, create a `.env` file and include the following variables:

```plaintext
MODAL_TOKEN_ID=<your_modal_token_id>
MODAL_TOKEN_SECRET=<your_modal_token_secret>
```

2. Run the desired make target based on your intended functionality. For example:

- To run the edmunds forum scraper, execute the following command:
  ```bash
  make edmunds_store
  ```

Note: Please ensure that you have the required environment set up by running the following command before executing any make target:
```bash
make environment
```

If you are working on development or generating the document corpus, you can use the `dev_environment` make target instead:
```bash
make dev_environment
```

For a comprehensive list of available make targets and their descriptions, run:
```bash
make help
```

Remember to refer to the respective sections in the `Makefile` for specific requirements and assumptions related to each make target.
