"""Exploration of the llm_sdk: tokens, ids, logits."""
import json
from llm_sdk import Small_LLM_Model


def main() -> None:
    model = Small_LLM_Model()

    # 1. Where is the vocab file? What does it look like?
    vocab_path = model.get_path_to_vocab_file()
    print("vocab path:", vocab_path)
    with open(vocab_path, encoding="utf-8") as f:
        vocab = json.load(f)
    print("vocab size:", len(vocab))
    print("first entries:", list(vocab.items())[:5])

    # 2. Encode a prompt: text -> token ids
    text = "What is the sum of 2 and 3?"
    ids = model.encode(text)
    print("\ninput ids:", ids)

    # 3. Decode back: ids -> text (round trip)
    print("decoded:", model.decode(ids.tolist() if hasattr(ids, "tolist") else ids))

    # 4. Logits: scores for EVERY possible next token
    flat = ids.tolist() if hasattr(ids, "tolist") else ids
    logits = model.get_logits_from_input_ids(flat)
    print("\nnb logits:", len(logits))
    top = sorted(range(len(logits)), key=lambda i: logits[i], reverse=True)[:10]
    id_to_token = {v: k for k, v in vocab.items()}
    for i in top:
        print(f"token {i} {id_to_token.get(i, '?')!r} -> {logits[i]:.3f}")


if __name__ == "__main__":
    main()

