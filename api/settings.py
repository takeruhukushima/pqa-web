import os
from dotenv import load_dotenv
from paperqa import Settings
from paperqa.settings import AgentSettings

load_dotenv()

class AppSettings:
    def __init__(self):
        self.gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not self.gemini_api_key:
            # In a server environment, we might not want to raise an exception at import time
            # but rather handle this gracefully when an API call is made.
            print("警告: 環境変数 'GEMINI_API_KEY' または 'GOOGLE_API_KEY' が設定されていません。")

        self.llm_name = "gemini-2.0-flash"
        self.embedding_name = "gemini/text-embedding-004"
        
        _api_dir = os.path.dirname(os.path.abspath(__file__))
        self.papers_directory = os.path.join(_api_dir, "my_papers")

    def get_paperqa_settings(self):
        from prompts import prompts  # Local import to avoid circular dependency

        paperqa_settings = Settings(
            llm=self.llm_name,
            summary_llm=self.llm_name,
            embedding=self.embedding_name,
            agent=AgentSettings(agent_llm=self.llm_name),
            paper_directory=self.papers_directory,
        )
        
        try:
            paperqa_settings.prompts.system = prompts.system
            paperqa_settings.prompts.qa = prompts.qa
            paperqa_settings.prompts.summary = prompts.summary
        except AttributeError as e:
            print(f"警告: プロンプト設定中にエラーが発生しました ({e})。デフォルトのプロンプトが使用される可能性があります。")
            
        return paperqa_settings

settings = AppSettings()
