PythonをバックエンドにもちFastAPIでWebUIのチャットインターフェースと接続されたアプリを作成します。
## Pythonの機能
paperqa を使い、UI上からアップロードしたファイルまたはフォルダからリトリーバルするRAGを作成します。
Pythonプログラムは以下を参考にしてください。

```python
import asyncio
import os
from dotenv import load_dotenv
from paperqa import Settings, ask
from paperqa.settings import AgentSettings
from datetime import datetime
import re

load_dotenv()

def clean_answer_text(text):
    """回答テキストから余計な情報を除去する関数"""
    if not text:
        return ""
    
    # 文字列に変換
    text = str(text)
    
    # "Question: ..." の行を除去
    text = re.sub(r'^Question:.*\n', '', text)
    
    # "References" 以降の部分を除去
    text = re.sub(r'\n\nReferences.*$', '', text, flags=re.DOTALL)
    
    # 複数の改行を整理
    text = re.sub(r'\n\s*\n', '\n\n', text)
    text = re.sub(r'^\s+|\s+$', '', text)
    
    return text.strip()

async def main():
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        gemini_api_key = os.getenv("GOOGLE_API_KEY")

    if not gemini_api_key:
        print("エラー: 環境変数 'GEMINI_API_KEY' または 'GOOGLE_API_KEY' が設定されていません。")
        print(".envファイルを作成し、APIキーを記述してください。")
        return

    question_to_ask_initially = "What is PaperQA2?" # 初期質問 (ループで上書き)
    papers_directory = "./my_papers"
    output_directory = "./out"

    gemini_llm_name = "gemini/gemini-2.5-flash"
    gemini_embedding_name = "gemini/text-embedding-004"

    os.makedirs(output_directory, exist_ok=True)

    print("PaperQA (Gemini版) チャットへようこそ！")
    print(f"論文は '{papers_directory}' ディレクトリから読み込みます。")
    print(f"回答は '{output_directory}' ディレクトリにMarkdownファイルとして保存されます。")
    print("質問を入力してください (終了するには 'exit' または 'quit' と入力)。")
    print("-" * 30)

    base_settings = Settings(
        llm=gemini_llm_name,
        summary_llm=gemini_llm_name,
        embedding=gemini_embedding_name,
        agent=AgentSettings(agent_llm=gemini_llm_name),
        paper_directory=papers_directory,
    )

    try:
        base_settings.prompts.system = (
            "あなたは優秀なAIアシスタントです。提供された学術論文のコンテキストに基づいて、ユーザーの質問に回答してください。"
            "回答は必ず日本語で行い、学術的な主張には必ず出典を明記してください。"
            "例：\n"
            "りんごは赤い[1]。\n\n"
            "参照文献:\n"
            "[1] 論文のタイトル, 著者, 出版年"
        )

        base_settings.prompts.qa = (
            "提供されたコンテキストのみに基づいて、以下の質問に答えてください。\n"
            "コンテキスト: {context}\n\n"
            "質問: {question}\n\n"
            "回答は必ず日本語で、簡潔に記述してください。"
            "学術的な主張には必ず{example_citation}形式で出典を明記してください。"
            "情報が不足している場合は「情報が不足しているため回答できません」と明確に述べてください。"
        )

        base_settings.prompts.summary = (
            "以下のテキストを、質問「{question}」との関連性を考慮して、日本語で要約してください。\n"
            "重要な主張には{citation}形式で出典を明記してください。\n"
            "テキスト: {text}"
        )
    except AttributeError as e:
        print(f"警告: プロンプト設定中にエラーが発生しました ({e})。デフォルトのプロンプトが使用される可能性があります。")

    while True:
        try:
            user_question = input("\nあなた: ")
            if user_question.lower() in ["exit", "quit", "終了", "ばいばい"]:
                print("チャットを終了します。")
                break
            if not user_question:
                continue

            print("\nPaperQA2: 考え中...")

            answer_response = await ask(
                query=user_question,
                settings=base_settings,
            )

            # 回答の取得ロジックを改善
            final_answer_text = None
            
            # 1. まず answer.answer 属性を確認（最も正確な回答が含まれている可能性が高い）
            if hasattr(answer_response, 'answer') and hasattr(answer_response.answer, 'answer'):
                final_answer_text = str(answer_response.answer.answer).strip()
                print("回答を 'answer.answer' 属性から取得しました。")
            # 2. 次に answer 属性を確認
            elif hasattr(answer_response, 'answer'):
                answer_obj = getattr(answer_response, 'answer')
                if answer_obj and str(answer_obj).strip():
                    final_answer_text = str(answer_obj).strip()
                    print("回答を 'answer' 属性から取得しました。")
            else:
                # 3. その他の属性を順番に確認
                possible_answer_attrs = [
                    'formatted_answer',
                    'text',
                    'content',
                    'response'
                ]
                
                for attr in possible_answer_attrs:
                    if hasattr(answer_response, attr):
                        attr_value = getattr(answer_response, attr)
                        if attr_value and str(attr_value).strip():
                            final_answer_text = str(attr_value).strip()
                            print(f"回答を '{attr}' 属性から取得しました。")
                            break
            
            # それでも見つからない場合は、オブジェクト全体を文字列化
            if not final_answer_text:
                final_answer_text = str(answer_response)
                print("回答をオブジェクト全体から取得しました。")
            
            # 回答テキストをクリーンアップ
            final_answer_text = clean_answer_text(final_answer_text)
            
            # 空の回答や意味のない回答をフィルタリング
            if not final_answer_text or final_answer_text in ["None", "", "回答が得られませんでした。"]:
                final_answer_text = "申し訳ありませんが、この質問に対する適切な回答を生成できませんでした。論文データベースに関連する情報が不足している可能性があります。"
            
            print(f"\nPaperQA2:\n{final_answer_text}")

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # ファイル名に使えない文字をアンダースコアに置換
            safe_question_part = "".join(c if c.isalnum() else "_" for c in user_question[:30])
            filename = os.path.join(output_directory, f"{timestamp}_{safe_question_part}.md")

            with open(filename, "w", encoding="utf-8") as f:
                f.write(f"# 質問: {user_question}\n\n")
                f.write(f"## 回答:\n")
                if hasattr(answer_response, 'answer'):
                    answer_text = str(answer_response.answer)
                    # answer='...' の形式から実際の回答のみを抽出
                    match = re.search(r"answer='(.*?)'", answer_text)
                    if match:
                        f.write(f"{match.group(1)}\n")
                    else:
                        f.write(f"{answer_text}\n")
                else:
                    f.write(f"{final_answer_text}\n")
                
                f.write(f"\n---\n*生成日時: {timestamp}*\n")
            
            print(f"回答を '{filename}' に保存しました。")

        except Exception as e:
            print(f"処理中にエラーが発生しました: {e}")
            import traceback
            traceback.print_exc()
            print("エラーが発生したため、この質問の処理を中断します。次の質問をどうぞ。")

if __name__ == "__main__":
    asyncio.run(main())
```
```python
Choosing Model
By default, PaperQA2 uses OpenAI's gpt-4o-2024-11-20 model for the summary_llm, llm, and agent_llm. Please see the Settings Cheatsheet for more information on these settings. PaperQA2 also defaults to using OpenAI's text-embedding-3-small model for the embedding setting. If you don't have an OpenAI API key, you can use a different embedding model. More information about embedding models can be found in the "Embedding Model" section.

We use the lmi package for our LLM interface, which in turn uses litellm to support many LLM providers. You can adjust this easily to use any model supported by litellm:

from paperqa import Settings, ask

answer_response = ask(
    "What is PaperQA2?",
    settings=Settings(
        llm="gpt-4o-mini", summary_llm="gpt-4o-mini", paper_directory="my_papers"
    ),
)
To use Claude, make sure you set the ANTHROPIC_API_KEY environment variable. In this example, we also use a different embedding model. Please make sure to pip install paper-qa[local] to use a local embedding model.

from paperqa import Settings, ask
from paperqa.settings import AgentSettings

answer_response = ask(
    "What is PaperQA2?",
    settings=Settings(
        llm="claude-3-5-sonnet-20240620",
        summary_llm="claude-3-5-sonnet-20240620",
        agent=AgentSettings(agent_llm="claude-3-5-sonnet-20240620"),
        # SEE: https://huggingface.co/sentence-transformers/multi-qa-MiniLM-L6-cos-v1
        embedding="st-multi-qa-MiniLM-L6-cos-v1",
    ),
)
Or Gemini, by setting the GEMINI_API_KEY from Google AI Studio

from paperqa import Settings, ask
from paperqa.settings import AgentSettings

answer_response = ask(
    "What is PaperQA2?",
    settings=Settings(
        llm="gemini/gemini-2.0-flash",
        summary_llm="gemini/gemini-2.0-flash",
        agent=AgentSettings(agent_llm="gemini/gemini-2.0-flash"),
        embedding="gemini/text-embedding-004",
    ),
)
Locally Hosted
You can use llama.cpp to be the LLM. Note that you should be using relatively large models, because PaperQA2 requires following a lot of instructions. You won't get good performance with 7B models.

The easiest way to get set-up is to download a llama file and execute it with -cb -np 4 -a my-llm-model --embedding which will enable continuous batching and embeddings.

from paperqa import Settings, ask

local_llm_config = dict(
    model_list=[
        dict(
            model_name="my_llm_model",
            litellm_params=dict(
                model="my-llm-model",
                api_base="http://localhost:8080/v1",
                api_key="sk-no-key-required",
                temperature=0.1,
                frequency_penalty=1.5,
                max_tokens=512,
            ),
        )
    ]
)

answer_response = ask(
    "What is PaperQA2?",
    settings=Settings(
        llm="my-llm-model",
        llm_config=local_llm_config,
        summary_llm="my-llm-model",
        summary_llm_config=local_llm_config,
    ),
)
Models hosted with ollama are also supported. To run the example below make sure you have downloaded llama3.2 and mxbai-embed-large via ollama.

from paperqa import Settings, ask

local_llm_config = {
    "model_list": [
        {
            "model_name": "ollama/llama3.2",
            "litellm_params": {
                "model": "ollama/llama3.2",
                "api_base": "http://localhost:11434",
            },
        }
    ]
}

answer_response = ask(
    "What is PaperQA2?",
    settings=Settings(
        llm="ollama/llama3.2",
        llm_config=local_llm_config,
        summary_llm="ollama/llama3.2",
        summary_llm_config=local_llm_config,
        embedding="ollama/mxbai-embed-large",
    ),
)

```
## ディレクトリ構造
バックエンドのディレクトリのルートにはsettings.pyとprompt.pyを追加してください。
settings.pyにはLLM関係の設定やインスタンスをクラスとして保存し、prompt.pyでは使用するプロンプトを全てクラスとして保存してください。

vercelにてデプロイするためVercel.json、.vercelignoreを以下の例に従って作成してください。
## Vecel.json
```json
{
    "version": 2,
    "builds": [
        {
            "src": "app.py",
            "use": "@vercel/python",
            "config": {
                "runtime": "python3.9",
                "pip_install_command": "pip install -r requirements.txt"
            }
        }
    ],
    "routes": [
        {
            "src": "/(.*)",
            "dest": "app.py"
        }
    ]
}
```
## .vercelignore
```.ignore
.vercel
.gitignore
LICENSE
README.md
venv
__pycache__
```
必要であれば他も追加すること




