# Third-party
from typing import Dict
import os
from pydantic_settings import BaseSettings
from pydantic import Field

class Vars(BaseSettings):
    key: str = Field(default_factory=lambda: os.getenv("TOKEN", ""))
    app_token: str = Field(default_factory=lambda: os.getenv("APP_KEY", ""))
    admin_list_var: str = Field(default_factory=lambda: os.getenv("ADMIN_LIST", ""))
    return_account: str = Field(default_factory=lambda: os.getenv("RETURN_ACCOUNT", ""))
    change_status: str = Field(default_factory=lambda: os.getenv("CHANGE_STATUS", ""))
    suspend_activate: str = Field(default_factory=lambda: os.getenv("SUSPEND_ACTIVATE", ""))
    extend_poc_7_days: str = Field(default_factory=lambda: os.getenv("EXTEND_POC_7_DAYS", ""))
    extend_poc_2_days: str = Field(default_factory=lambda: os.getenv("EXTEND_POC_2_DAYS", ""))
    change_tier: str = Field(default_factory=lambda: os.getenv("CHANGE_TIER", ""))
    trial_started_last_7_days: str = Field(default_factory=lambda: os.getenv("TRIAL_STARTED_LAST_7_DAYS", ""))
    trial_about_end: str = Field(default_factory=lambda: os.getenv("TRIAL_ABOUT_END", ""))
    trial_in_progress: str = Field(default_factory=lambda: os.getenv("TRIAL_IN_PROGRESS", ""))
    get_id: str = Field(default_factory=lambda: os.getenv("GET_ID", ""))
    auth0_doamin: str = Field(default_factory=lambda: os.getenv("AUTH0_DOMAIN", ""))
    client_id: str = Field(default_factory=lambda: os.getenv("CLIENT_ID", ""))
    client_secret: str = Field(default_factory=lambda: os.getenv("CLIENT_SECRET", ""))
    api_key_deals: str = Field(default_factory=lambda: os.getenv("API_KEY_DEALS", ""))
    deals_api_url: str = Field(default_factory=lambda: os.getenv("DEALS_API_URL", ""))
    owners_api_url: str = Field(default_factory=lambda: os.getenv("OWNERS_API_URL", ""))
    AZURE_API_KEY: str = Field(default_factory=lambda: os.getenv("AZURE_API_KEY", ""))
    AZURE_OPENAI_ENDPOINT: str = Field(default_factory=lambda: os.getenv("AZURE_OPENAI_ENDPOINT", ""))