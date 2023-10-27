"""Implementation derived from https://github.com/tloen/alpaca-lora"""
import json
import sys
from pathlib import Path
from typing import Optional

import requests
import torch
from torch.utils.data import random_split
from tqdm import tqdm

from transformers import AutoTokenizer


def prepare(
        destination_path: Path = Path("data"),
        checkpoint_dir: str = "stabilityai/stablelm-base-alpha-3b",
        test_split_fraction: float = 0.03865,  # to get exactly 2000 test samples,
        seed: int = 42,
        mask_inputs: bool = False,  # as in alpaca-lora
        data_file_name: str = "edmunds_forum.json",
        data_file_url: str = "https://storage.googleapis.com/public_bkt/edmunds_forum.json",
        ignore_index: int = -1,
        max_seq_length: Optional[int] = None,
) -> dict:
    """Prepare the Alpaca dataset for instruction tuning.

    The output is a training and test dataset saved as `train.pt` and `test.pt`,
    which stores the preprocessed and tokenized prompts and labels.
    """
    if max_seq_length is None:
        raise AttributeError("No max sey length found")

    destination_path.mkdir(parents=True, exist_ok=True)
    data_file_path = destination_path / data_file_name
    print("Loading data file...")
    download_if_missing(data_file_path, data_file_url)
    with open(data_file_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    print("Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(checkpoint_dir)

    # Partition the dataset into train and test
    train_set, test_set = random_split(
        data, [1.0 - test_split_fraction, test_split_fraction], generator=torch.Generator().manual_seed(seed)
    )
    train_set, test_set = list(train_set), list(test_set)

    print(f"train has {len(train_set):,} samples")
    print(f"test has {len(test_set):,} samples")

    print("Processing train split ...")
    train_set = [
        prepare_sample(
            example=sample,
            tokenizer=tokenizer,
            max_length=max_seq_length,
            mask_inputs=mask_inputs,
            ignore_index=ignore_index,
        )
        for sample in tqdm(train_set)
    ]
    torch.save(train_set, destination_path / "train.pt")

    print("Processing test split ...")
    test_set = [
        prepare_sample(
            example=sample,
            tokenizer=tokenizer,
            max_length=max_seq_length,
            mask_inputs=mask_inputs,
            ignore_index=ignore_index,
        )
        for sample in tqdm(test_set)
    ]
    torch.save(test_set, destination_path / "test.pt")

    return {
        'train': train_set,
        'test': test_set
    }


def download_if_missing(file_path: Path, file_url: str) -> None:
    """Downloads the raw json data file and saves it in the given destination."""
    if file_path.exists() and file_path.stat().st_size > 0:
        return
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(requests.get(file_url).text)


def prepare_sample(example: dict, tokenizer: AutoTokenizer, max_length: int, mask_inputs: bool,
                   ignore_index: int) -> dict:
    """Processes a single sample.

    Each sample in the dataset consists of:
    - instruction: A string describing the task
    - input: A string holding a special input value for the instruction.
        This only applies to some samples, and in others this is empty.
    - output: The response string

    This function processes this data to produce a prompt text and a label for
    supervised training. The prompt text is formed as a single message including both
    the instruction and the input. The label/target is the same message but with the
    response attached.

    Finally, both the prompt and the label get tokenized. If desired, all tokens
    in the label that correspond to the original input prompt get masked out (default).
    """
    full_prompt = generate_prompt(example)
    full_prompt_and_response = full_prompt + example["response"]
    encoded_full_prompt = tokenizer.encode(full_prompt, max_length=max_length)
    encoded_full_prompt_and_response = tokenizer.encode(full_prompt_and_response, max_length=max_length)

    # The labels are the full prompt with response, but with the prompt masked out
    labels = encoded_full_prompt_and_response[:]
    if mask_inputs:
        labels[: len(encoded_full_prompt)] = ignore_index

    return {
        **example,
        "input_ids": encoded_full_prompt_and_response,
        "input_ids_no_response": encoded_full_prompt,
        "labels": labels,
    }


def prepare_data(row, context_length=50):
    instructions = []
    comments = list(row.comments)

    if not comments:
        return None

    comments = comments[::-1]
    comments_len = len(comments)

    instructions.append({
        "instruction": row.title + "\n" + row.description,
        "context": "",
        "response": comments[0]['comment_text']
    })

    for i in range(0, comments_len - 1):
        past_idx = -int(min(len(instructions), context_length))
        past_context = '\n'.join([inst['response'] for inst in instructions[past_idx:]])

        instruction = {
            "instruction": instructions[-1]['response'],
            "context": past_context,
            "response": comments[i]['comment_text']
        }

        instructions.append(instruction)

    return instructions


def generate_prompt(example: dict) -> str:
    """Generates a standardized message to prompt the model with an instruction, optional input and a
    'response' field."""

    if example["context"]:
        return (
            "Below is an instruction that describes a task, paired with an input that provides further context. "
            "Write a response that appropriately completes the request.\n\n"
            f"### Instruction:\n{example['instruction']}\n\n### Input:\n{example['context']}\n\n### Response:"
        )
    return (
        "Below is an instruction that describes a task. "
        "Write a response that appropriately completes the request.\n\n"
        f"### Instruction:\n{example['instruction']}\n\n### Response:"
    )
