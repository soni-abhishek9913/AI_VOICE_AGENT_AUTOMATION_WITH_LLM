import torch, tiktoken, argparse, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from config import default_config as config
from transformer import Transformer


def generate_text(model_path: str, prompt: str, max_new_tokens: int = 200,
                  temperature: float = 0.8, top_k: int = 40, device: str = 'cuda') -> str:
    ckpt  = torch.load(model_path, map_location=device)
    model = Transformer(config['n_head'], config['n_embed'], config['context_length'],
                        config['vocab_size'], config['n_blocks'])
    model.load_state_dict(ckpt['model_state_dict'])
    model.eval().to(device)

    enc     = tiktoken.get_encoding("r50k_base")
    context = torch.tensor(enc.encode_ordinary(prompt), dtype=torch.long, device=device).unsqueeze(0)

    print(f"Prompt: {prompt!r}\nGenerating {max_new_tokens} tokens...\n" + "─" * 50)
    with torch.no_grad():
        out = model.generate(context, max_new_tokens, temperature, top_k)[0].tolist()
    return enc.decode(out)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument('--model_path',     required=True)
    p.add_argument('--input_text',     required=True)
    p.add_argument('--max_new_tokens', type=int,   default=200)
    p.add_argument('--temperature',    type=float, default=0.8)
    p.add_argument('--top_k',          type=int,   default=40)
    p.add_argument('--device',         default=config['device'])
    args = p.parse_args()
    print(generate_text(args.model_path, args.input_text,
                        args.max_new_tokens, args.temperature, args.top_k, args.device))


if __name__ == "__main__":
    main()