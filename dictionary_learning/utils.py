from datasets import load_dataset
import zstandard as zstd
import io
import json
import os
from nnsight import LanguageModel

from .trainers.top_k import AutoEncoderTopK
from .trainers.batch_top_k import BatchTopKSAE
from .trainers.matryoshka_batch_top_k import MatryoshkaBatchTopKSAE
from .trainers.vsae_iso import VSAEIsoGaussian
from .dictionary import (
    AutoEncoder,
    GatedAutoEncoder,
    AutoEncoder,
    JumpReluAutoEncoder,
)

def hf_dataset_to_generator(dataset_name, split="train", streaming=True, return_tokens=False):
    dataset = load_dataset(dataset_name, split=split, streaming=streaming)

    def gen():
        for x in iter(dataset):
            if return_tokens:
                if "tokens" in x:
                    # print({k: type(v) for k, v in x.items()})
                    yield {"tokens": x["tokens"]}
                else:
                    raise KeyError("'tokens' not found.")
            else:
                if "text" in x:
                    yield x["text"]
                else:
                    raise KeyError("'text' not found. Try return_tokens=True.")

    return gen()



def zst_to_generator(data_path):
    """
    Load a dataset from a .jsonl.zst file.
    The jsonl entries is assumed to have a 'text' field
    """
    compressed_file = open(data_path, "rb")
    dctx = zstd.ZstdDecompressor()
    reader = dctx.stream_reader(compressed_file)
    text_stream = io.TextIOWrapper(reader, encoding="utf-8")

    def generator():
        for line in text_stream:
            yield json.loads(line)["text"]

    return generator()


def get_nested_folders(path: str) -> list[str]:
    """
    Recursively get a list of folders that contain an ae.pt file, starting the search from the given path
    """
    folder_names = []

    for root, dirs, files in os.walk(path):
        if "ae.pt" in files:
            folder_names.append(root)

    return folder_names


def load_dictionary(base_path: str, device: str) -> tuple:
    ae_path = f"{base_path}/ae.pt"
    config_path = f"{base_path}/config.json"

    with open(config_path, "r") as f:
        config = json.load(f)

    dict_class = config["trainer"]["dict_class"]

    if dict_class == "AutoEncoder":
        dictionary = AutoEncoder.from_pretrained(ae_path, device=device)
    elif dict_class == "GatedAutoEncoder":
        dictionary = GatedAutoEncoder.from_pretrained(ae_path, device=device)
    elif dict_class == "AutoEncoder":
        dictionary = AutoEncoder.from_pretrained(ae_path, device=device)
    elif dict_class == "AutoEncoderTopK":
        k = config["trainer"]["k"]
        dictionary = AutoEncoderTopK.from_pretrained(ae_path, k=k, device=device)
    elif dict_class == "BatchTopKSAE":
        k = config["trainer"]["k"]
        dictionary = BatchTopKSAE.from_pretrained(ae_path, k=k, device=device)
    elif dict_class == "MatryoshkaBatchTopKSAE":
        k = config["trainer"]["k"]
        dictionary = MatryoshkaBatchTopKSAE.from_pretrained(ae_path, k=k, device=device)
    elif dict_class == "JumpReluAutoEncoder":
        dictionary = JumpReluAutoEncoder.from_pretrained(ae_path, device=device)
    elif dict_class == "VSAEIsoGaussian":
        dictionary = VSAEIsoGaussian.from_pretrained(ae_path, device=device)
    else:
        raise ValueError(f"Dictionary class {dict_class} not supported")

    return dictionary, config


def get_submodule(model: LanguageModel, layer: int):
    """Gets the residual stream submodule"""
    model_name = model._model_key

    if "pythia" in model_name:
        return model.gpt_neox.layers[layer]
    elif "gemma" in model_name:
        return model.model.layers[layer]
    else:
        raise ValueError(f"Please add submodule for model {model_name}")
