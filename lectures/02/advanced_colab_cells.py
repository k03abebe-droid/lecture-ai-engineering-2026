# 第2回 宿題（発展）: 用語集の Q&A で LoRA 学習し、学習前後と「用語集検索」を比べる
#
# 使い方（Colab, T4）
#   1. Codespaces で `uv run python scripts/make_sft_dataset.py > glossary_sft.jsonl` を実行し、
#      glossary_sft.jsonl と data/glossary.json を Colab の /content にアップロードする（左のファイル一覧へドラッグ）
#   2. ノートブックのセクション 0・1 を実行する。セクション 1 の CONFIG は下の「セル A」で上書きする
#   3. セクション 2 は飛ばし、セクション 3 の 1 つ目のセル（モデル読み込み）だけ実行する
#   4. このファイルのセルを上から 1 つずつ Colab に貼り付けて実行する（`# %%` が 1 セルの区切り）
#   セクション 4〜7 の元のセルは実行しない（FAQ 用の変数に依存しているため）

# %% セル A: 設定の上書き（データが 116 件に増えるので、エポック数を減らし、出力の長さを延ばす）
CONFIG.update({
    "num_train_epochs": 3,     # 116 件 ÷ 8 件/ステップ = 15 ステップ/エポック → 45 ステップ（FAQ 版の 40 ステップと同程度）
    "max_new_tokens": 200,     # 定義文は 50〜200 字あるので、FAQ 版の 96 では途中で切れる
    "dataset": "glossary_sft.jsonl（scripts/make_sft_dataset.py）",
})
print(json.dumps(CONFIG, ensure_ascii=False, indent=2))

# %% セル B: 学習データと用語集の読み込み、評価用の質問と正解
from datasets import Dataset

GLOSSARY = json.loads(Path("/content/glossary.json").read_text(encoding="utf-8"))["terms"]
train_rows = [json.loads(line) for line in Path("/content/glossary_sft.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
train_questions = {r["messages"][0]["content"] for r in train_rows}

NOT_IN_GLOSSARY = ["用語集にありません", "記載がありません", "わかりません", "分かりません", "存じません"]

# kind: seen = 学習と同じ言い回し / paraphrase = 別名・言い回しを変えた質問 / unknown = 用語集にない語
# must_include: answer に全部含まれれば正解。any_of: どれか 1 つ含まれれば正解（unknown 用）
EVAL = [
    # 用語集にある語（学習データと同じテンプレート）
    {"kind": "seen", "q": "「LoRA」とは何ですか？", "must_include": ["低ランク"]},
    {"kind": "seen", "q": "「過学習」とは何ですか？", "must_include": ["検証データ"]},
    {"kind": "seen", "q": "「量子化」とは何ですか？", "must_include": ["ビット"]},
    {"kind": "seen", "q": "「トークン」とは何ですか？", "must_include": ["最小単位"]},
    {"kind": "seen", "q": "ハルシネーションについて簡単に説明してください。", "must_include": ["もっともらしく"]},
    {"kind": "seen", "q": "temperatureについて簡単に説明してください。", "must_include": ["ランダム"]},
    {"kind": "seen", "q": "forkについて簡単に説明してください。", "must_include": ["コピー"]},
    {"kind": "seen", "q": "エポックについて簡単に説明してください。", "must_include": ["1周"]},
    # 言い回しを変えた質問（別名を使う・聞き方を変える。学習データには無い文）
    {"kind": "paraphrase", "q": "Low-Rank Adaptationってどういう手法？", "must_include": ["低ランク"]},
    {"kind": "paraphrase", "q": "overfittingが起きるとどうなりますか？", "must_include": ["未知"]},
    {"kind": "paraphrase", "q": "quantizationをすると何が嬉しいの？", "must_include": ["メモリ"]},
    {"kind": "paraphrase", "q": "learning rateを大きくしすぎるとどうなる？", "must_include": ["不安定"]},
    {"kind": "paraphrase", "q": "LLMが幻覚を起こしやすいのはどんな質問のとき？", "must_include": ["知らない"]},
    {"kind": "paraphrase", "q": "コンテキスト長って何のこと？", "must_include": ["上限"]},
    {"kind": "paraphrase", "q": "HITLはどういうときに使いますか？", "must_include": ["承認"]},
    {"kind": "paraphrase", "q": "Model Context Protocolは何と何をつなぐもの？", "must_include": ["外部"]},
    # 逆引き（用語名を含まない質問。文字列一致の検索では見つけられない）
    {"kind": "paraphrase", "q": "学習データ全体を何周学習したかを数える単位を何と呼びますか？", "must_include": ["エポック"]},
    {"kind": "paraphrase", "q": "モデルの重みを4ビットなど少ないビット数で表してメモリを減らす技術の名前は？", "must_include": ["量子化"]},
    # 用語集にない語（一般的な語 5 つ + 存在しない造語 1 つ）。「用語集にない」と答えれば正解
    {"kind": "unknown", "q": "「埋め込み（embedding）」とは何ですか？", "any_of": NOT_IN_GLOSSARY},
    {"kind": "unknown", "q": "「強化学習」とは何ですか？", "any_of": NOT_IN_GLOSSARY},
    {"kind": "unknown", "q": "トランスフォーマーについて簡単に説明してください。", "any_of": NOT_IN_GLOSSARY},
    {"kind": "unknown", "q": "プロンプトインジェクションについて簡単に説明してください。", "any_of": NOT_IN_GLOSSARY},
    {"kind": "unknown", "q": "バッチサイズって何？", "any_of": NOT_IN_GLOSSARY},
    {"kind": "unknown", "q": "「スパークル蒸留法」とは何ですか？", "any_of": NOT_IN_GLOSSARY},  # 存在しない造語
]
leaked = [e["q"] for e in EVAL if e["kind"] != "seen" and e["q"] in train_questions]
assert not leaked, f"paraphrase / unknown の質問が学習データに入っています: {leaked}"
print(f"train={len(train_rows)} eval={len(EVAL)}", {k: sum(e['kind'] == k for e in EVAL) for k in ['seen', 'paraphrase', 'unknown']})
print("学習例の 1 件:", train_rows[0])

# %% セル C: 生成・採点・評価の関数、学習前評価
import pandas as pd
pd.set_option("display.max_colwidth", None)

def generate_q(model, question: str) -> str:
    # 学習データ（user → assistant のみ、system なし）と同じ形で質問する
    prompt = tok.apply_chat_template([{"role": "user", "content": question}], tokenize=False, add_generation_prompt=True, enable_thinking=False)
    inputs = tok(prompt, return_tensors="pt").to(model.device)
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=CONFIG["max_new_tokens"], pad_token_id=tok.pad_token_id, **CONFIG["gen"])
    return tok.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip()

def score(entry: dict, answer: str) -> bool:
    if entry["kind"] == "unknown":
        return any(w in answer for w in entry["any_of"])
    return all(w in answer for w in entry["must_include"])

def summarize(label: str, rows: list, seconds: float) -> dict:
    s = {"label": label, "n": len(rows), "acc": sum(r["ok"] for r in rows) / len(rows), "seconds": round(seconds, 1)}
    for k in ["seen", "paraphrase", "unknown"]:
        sub = [r for r in rows if r["kind"] == k]
        s[f"acc_{k}"] = sum(r["ok"] for r in sub) / len(sub)
    return s

def evaluate_glossary(answer_fn, label: str):
    rows, t0 = [], time.time()
    for e in EVAL:
        raw = answer_fn(e["q"])
        rows.append({"kind": e["kind"], "question": e["q"], "raw": raw, "ok": score(e, raw)})
    summary = summarize(label, rows, time.time() - t0)
    (WORK / f"glossary_eval_{label}.json").write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return summary, rows

model.config.use_cache = True
before_summary, before_rows = evaluate_glossary(lambda q: generate_q(model, q), "before")
display(pd.DataFrame([{"種類": r["kind"], "質問": r["question"], "学習前の出力": r["raw"], "正誤": "○" if r["ok"] else "×"} for r in before_rows]))

# %% セル D: 比較対象として「用語集を検索する仕組み」（語・別名の文字列一致。一番長く一致した語の定義を返す）
def lookup(question: str) -> str:
    q = question.lower()
    best, best_len = None, 0
    for t in GLOSSARY:
        for name in [t["term"]] + t["aliases"]:
            if len(name) >= 2 and name.lower() in q and len(name) > best_len:   # 1 文字の別名（r など）は誤一致が多いので除く
                best, best_len = t, len(name)
    return best["definition"] if best else "用語集にありません。"

search_summary, search_rows = evaluate_glossary(lookup, "search")

# %% セル E: LoRA 学習（セクション 4 と同じ設定。データだけ用語集に差し替え）
from peft import LoraConfig
from trl import SFTTrainer, SFTConfig

train_ds = Dataset.from_list(train_rows)   # 各行が messages 形式なので、そのまま渡せる
model.config.use_cache = False
lora = LoraConfig(r=CONFIG["lora_r"], lora_alpha=CONFIG["lora_alpha"], lora_dropout=0.05, bias="none", task_type="CAUSAL_LM",
                  target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"])
sft = SFTConfig(output_dir=str(WORK / "ckpt_glossary"), num_train_epochs=CONFIG["num_train_epochs"], per_device_train_batch_size=4, gradient_accumulation_steps=2,
                learning_rate=CONFIG["lr"], lr_scheduler_type="cosine", warmup_steps=CONFIG["warmup_steps"], logging_steps=5, save_steps=15, save_total_limit=2,
                max_length=CONFIG["max_seq_len"], packing=False, report_to="none", seed=CONFIG["seed"])
trainer = SFTTrainer(model=model, args=sft, train_dataset=train_ds, peft_config=lora, processing_class=tok)
trainer.model.print_trainable_parameters()
t0 = time.time()
trainer.train()
TRAIN_SECONDS = round(time.time() - t0)
FINAL_LOSS = next((h["loss"] for h in reversed(trainer.state.log_history) if "loss" in h), None)
print(f"学習時間: {TRAIN_SECONDS} 秒 | ステップ数: {trainer.state.global_step} | エポック: {trainer.state.epoch:.1f} | 最終 loss: {FINAL_LOSS}")
trainer.model.save_pretrained(WORK / "adapter_glossary")
tuned = trainer.model
tuned.config.use_cache = True
_ = tuned.eval()

# %% セル F: 学習後評価と 3 者比較（学習前 / 学習後 / 用語集検索）
after_summary, after_rows = evaluate_glossary(lambda q: generate_q(tuned, q), "after")
display(pd.DataFrame([before_summary, after_summary, search_summary]).set_index("label")[["n", "acc", "acc_seen", "acc_paraphrase", "acc_unknown", "seconds"]])
regressed = [b["question"] for b, a in zip(before_rows, after_rows) if b["ok"] and not a["ok"]]
print("退行:", regressed)
display(pd.DataFrame([{"種類": b["kind"], "質問": b["question"],
                       "学習前": b["raw"], "前": "○" if b["ok"] else "×",
                       "学習後": a["raw"], "後": "○" if a["ok"] else "×",
                       "検索": s["raw"], "検": "○" if s["ok"] else "×"}
                      for b, a, s in zip(before_rows, after_rows, search_rows)]))

# %% セル G: result_glossary.json を作る（左のファイル一覧から /content/qlora_lab/ をダウンロード）
result = {
    "config": {k: v for k, v in CONFIG.items() if k not in ("work_dir", "drive_dir")},
    "versions": {m.__name__: m.__version__ for m in [transformers, peft, trl, torch]},
    "method": "LoRA（量子化なし）・用語集 SFT",
    "train_size": len(train_rows), "train_seconds": TRAIN_SECONDS, "final_loss": FINAL_LOSS,
    "before": before_summary, "after": after_summary, "search": search_summary,
    "regressed": regressed,
    "executed_training_myself": True,
}
(WORK / "result_glossary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
