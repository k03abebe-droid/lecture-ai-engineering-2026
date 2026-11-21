# 第5回 解答

## 演習

- `--list-tools` で見えたツール名と、第3回（`--mcp` なし）との違い：
  - 第3回：`search_glossary`、`get_lecture_summary`（2個）
  - 第5回（演習3の前）：`glossary_search_glossary`（1個）
  - MCP 経由では名前に「サーバー名_」が付く。説明文は `app/tools.py` の docstring と同じで、引数のスキーマには `title` が増えていた
- `--mcp --trace` で見えたツール呼び出し（ツール名と引数）と、`requests` の回数：
  - 質問：「AIE2026の講座の宿題にある「3レベル」とは何ですか？」
  - 第3回：`search_glossary({'query': '3レベル'})`、`requests=2`、`tool_calls=1`、入力 783 トークン
  - 第5回：`glossary_search_glossary({'query': '3レベル'})`、`requests=2`、`tool_calls=1`、入力 651 トークン
  - 回答の内容は同じ（基礎・実装・発展のどれか1つ）。入力トークンが少ないのは、この時点の MCP 側のツールが1個だったためと考えられる
- MCP サーバーに公開したツールと、その説明文：
  - `get_lecture_summary`（一覧では `glossary_get_lecture_summary`）を `server.tool()(tools.get_lecture_summary)` で公開した
  - 説明文：「指定した回（1始まりの整数）の講義の要点を返す。「第3回では何を学ぶ？」のように、回の内容や関係を聞かれたときに使う。」
  - 「第2回では何を学びますか？」で `glossary_get_lecture_summary({'lecture': 2})` が呼ばれた（`requests=2`、`tool_calls=1`）
- fetch サーバーを足したときのツール呼び出し（ツール名と引数）：
  - `app/mcp_servers.json` の変更だけで `fetch_fetch` が増え、ツールは3個になった
  - `fetch_fetch({'url': 'https://modelcontextprotocol.io/'})` のあと、`glossary_search_glossary({'query': 'MCP'})` が呼ばれた（`requests=3`、`tool_calls=2`、入力 4286 トークン）
  - fetch は `robots.txt` を確認し、307 リダイレクトをたどって本文を取得していた。ページ本文が入力に入るため、トークン数が大きく増えた

## 宿題

- 取り組んだレベル：発展
- やったこと：
  - `.vscode/mcp.json` を作り、同じ用語集サーバーを Copilot Chat（Agent モード）から使った
  - 同じ質問「AIE2026 の宿題の 3 レベルとは？」を、Copilot Chat と `app/agent.py` の両方で実行して比べた
  - `.vscode/mcp.json` と同じコマンドでサーバーを起動し、`initialize` → `tools/list` → `tools/call` の応答を確認した
- 結果：

  | 比べる点 | エージェント（`app/agent.py --mcp`） | Copilot Chat |
  |---|---|---|
  | 設定ファイル | `app/mcp_servers.json`（`mcpServers`） | `.vscode/mcp.json`（`servers`） |
  | 誰がサーバーを起動するか | `app.agent` がサブプロセスとして起動 | VS Code が `.vscode/mcp.json` に従って起動 |
  | ツール名 | `glossary_search_glossary` | `search_glossary` |
  | 呼び出し前の人の承認 | なし | あり（実行前に Continue の確認が出て、許可すると実行された） |
  | 呼び出しの引数 | `{'query': '3レベル'}` | `{"query": "宿題"}` |
  | 結果の見え方 | `--trace` に tool call / tool return / usage を表示 | Chat にツール名と入力が `Completed with input` として表示され、続けて回答が出る |
  | 回答 | 基礎・実装・発展のどれか1つに取り組む | 同じ3レベルに加えて、`answer.md` と PR による提出方法も説明 |

  エージェント側の `--trace`：

  ```text
  [tool call]   glossary_search_glossary({'query': '3レベル'})
  [tool return] glossary_search_glossary -> [{"term": "宿題の3レベル", "lecture": 1, ...
  [usage] input_tokens=1435, output_tokens=135, requests=2, tool_calls=1
  ```

  Copilot Chat に表示されたツール呼び出し：

  ```text
  Search Tools

  search_glossary
  Completed with input: {
    "query": "宿題"
  }
  ```

- 気づき・疑問：
  - サーバーのコードは変えず、クライアント側の設定だけで接続先のアプリを替えられる
  - サーバーが公開するツール名は `search_glossary` で、`glossary_` はエージェント側が付けた接頭辞だった
  - 存在しない回（第99回）を指定すると、`isError=false` の通常の結果として「まだありません」が返る。モデルはこの文章を読んで次の行動を決める
  - 同じサーバーと同じ趣旨の質問でも、モデルが選ぶ検索語は違った（エージェントは「3レベル」、Copilot は「宿題」）
  - 「宿題」で検索すると「宿題の3レベル」「ADK」「answer.md」の3件が返る。Copilot の回答にある提出方法は、このうち `answer.md` の項目の内容と一致する
  - 検索語が広いと関係の薄い項目（ADK）も返るので、ツールの説明文で検索語の選び方を伝えることが大事だと分かった
