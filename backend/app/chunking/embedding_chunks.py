

"""
Điền embedding (text-embedding-3-small, 1536 chiều) cho các dòng doc_chunks chưa có embedding.
Embed đúng cột `embed_text`; ghi lại `token_count` (số token của embed_text).

Cài đặt:  pip install openai supabase tiktoken
Biến môi trường:  OPENAI_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
Chạy:     python embed_chunks.py
Chạy lại được nhiều lần (chỉ xử lý dòng embedding IS NULL).
"""
import os, sys
import tiktoken
from openai import OpenAI
from supabase import create_client

from dotenv import load_dotenv
load_dotenv()

MODEL = "text-embedding-3-small"
BATCH = 50
sb = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_SERVICE_ROLE_KEY"],
)
oa = OpenAI()
enc = tiktoken.get_encoding("cl100k_base")   # tokenizer của text-embedding-3-*

done = 0
while True:
    rows = (sb.table("doc_chunks").select("id,embed_text")
              .is_("embedding", "null").order("id").limit(BATCH).execute().data)
    if not rows:
        break
    resp = oa.embeddings.create(model=MODEL, input=[r["embed_text"] for r in rows])
    for r, d in zip(rows, resp.data):
        vec = "[" + ",".join(f"{x:.8f}" for x in d.embedding) + "]"   # dạng text, PostgREST ép sang vector
        sb.table("doc_chunks").update({
            "embedding": vec,
            "token_count": len(enc.encode(r["embed_text"])),
        }).eq("id", r["id"]).execute()
    done += len(rows)
    print(f"đã embed {done} dòng", flush=True)

left = sb.table("doc_chunks").select("id", count="exact ").is_("embedding", "null").execute().count
sys.exit(0 if left == 0 else 1)