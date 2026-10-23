"""CLIP zero-shot: which main character is visible in the left (film) panel, 1 frame per second.
usage: who_is_in_frame.py <ffmpeg> <ep.mkv> <out.npy>   -> float32 [seconds, len(LABELS)] softmax probs"""
import sys, subprocess, numpy as np, torch, open_clip

LABELS = ["an anime young man with messy blond hair",
          "an anime girl with black hair in a ponytail and bangs",
          "an anime young man with short black hair",
          "an anime girl with curly orange hair and round glasses",
          "an anime young man with spiky red hair",
          "an anime girl with wavy blond hair",
          "an anime background scenery without people",
          "several anime people standing together"]
ffmpeg, src, out = sys.argv[1:4]
model, _, _ = open_clip.create_model_and_transforms("ViT-B-32", pretrained="openai"); model.eval()
tok = open_clip.get_tokenizer("ViT-B-32")
mean = torch.tensor([0.48145466, 0.4578275, 0.40821073]).view(1, 3, 1, 1)
std = torch.tensor([0.26862954, 0.26130258, 0.27577711]).view(1, 3, 1, 1)
with torch.no_grad():
    T = model.encode_text(tok(LABELS)); T /= T.norm(dim=-1, keepdim=True)
p = subprocess.Popen([ffmpeg, "-v", "error", "-i", src, "-an", "-sn", "-vf", "fps=1,crop=1344:1080,scale=224:224",
                      "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
n = 224 * 224 * 3
res, buf = [], []


def flush():
    if not buf:
        return
    x = torch.from_numpy(np.stack(buf)).permute(0, 3, 1, 2).float() / 255.0
    x = (x - mean) / std
    with torch.no_grad():
        v = model.encode_image(x); v /= v.norm(dim=-1, keepdim=True)
        res.append((100 * v @ T.T).softmax(-1).numpy())
    buf.clear()


while True:
    b = p.stdout.read(n)
    if len(b) < n:
        break
    buf.append(np.frombuffer(b, np.uint8).reshape(224, 224, 3))
    if len(buf) == 64:
        flush()
flush()
np.save(out, np.concatenate(res).astype(np.float32))
print(src, sum(len(r) for r in res))
