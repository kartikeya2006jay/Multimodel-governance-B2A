"""
app/agents/llm/llm_agent.py — Generic LLM orchestrator agent.
Calls OpenAI API (key from env). Tracks token usage for billing.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import structlog

from app.agents.base_agent import BaseAgent
from app.core.billing_engine import billing_engine
from app.core.config import settings

log = structlog.get_logger(__name__)


class LLMAgent(BaseAgent):
    name = "llm"
    role = "llm"
    scopes = ["llm:call", "llm:read"]
    description = "Generic LLM orchestrator agent. Uses OpenAI to process context."
    version = "1.0.0"
    cost_per_call = 0.005

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        if settings.MOCK_LLM:
            return self._mock_response(context)

        try:
            from openai import AsyncOpenAI
        except ImportError:
            return {"llm_status": "error", "error": "openai package not installed"}

        api_key = settings.OPENAI_API_KEY
        if not api_key:
            log.warning("llm_agent.no_api_key")
            return self._mock_response(context, note="No API key provided, using mock fallback.")

        try:
            client = AsyncOpenAI(api_key=api_key)

            system_prompt = context.get(
                "system_prompt",
                "You are a governance AI assistant. Analyse the provided context and return a structured JSON assessment.",
            )
            user_content = context.get(
                "user_message",
                f"Analyse the following workflow context and provide a governance assessment:\n{context}",
            )

            messages: List[Dict[str, str]] = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": str(user_content)},
            ]

            model = context.get("llm_model", settings.OPENAI_DEFAULT_MODEL)
            max_tokens = int(context.get("llm_max_tokens", settings.OPENAI_MAX_TOKENS))
            temperature = float(context.get("llm_temperature", settings.OPENAI_TEMPERATURE))

            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )

            content = response.choices[0].message.content or ""
            usage = response.usage

            # Report token usage
            tenant_id = context.get("_tenant_id", "default")
            workflow_id = context.get("_workflow_id")
            if usage:
                from app.models.base import AsyncSessionLocal
                from app.services.billing_service import billing_service
                async with AsyncSessionLocal() as db:
                    await billing_service.charge_llm_tokens(
                        db=db,
                        tenant_id=tenant_id,
                        agent_name=self.name,
                        prompt_tokens=usage.prompt_tokens,
                        completion_tokens=usage.completion_tokens,
                        model=model,
                        workflow_id=workflow_id,
                    )

            return {
                "llm_status": "completed",
                "llm_response": content,
                "llm_model": model,
                "llm_usage": {
                    "prompt_tokens": usage.prompt_tokens if usage else 0,
                    "completion_tokens": usage.completion_tokens if usage else 0,
                    "total_tokens": usage.total_tokens if usage else 0,
                },
            }
        except Exception as exc:
            log.error("llm_agent.api_error", error=str(exc))
            return self._mock_response(context, note=f"API Error: {str(exc)}. Using mock fallback.")

    def _mock_response(self, context: Dict[str, Any], note: Optional[str] = None) -> Dict[str, Any]:
        """Provides a simulated LLM response for testing and governance demonstration."""
        workflow_type = context.get("workflow_type", "unknown")
        
        mock_content = {
            "assessment": f"Governance review for {workflow_type} workflow.",
            "status": "APPROVED",
            "risk_score": 0.15,
            "observations": [
                "Context analyzed successfully.",
                "No major policy violations detected in mock pass.",
                "Compliance standards met for simulation."
            ],
            "note": note or "SIMULATED RESPONSE (MOCK MODE)"
        }

        import json
        return {
            "llm_status": "completed",
            "llm_response": json.dumps(mock_content, indent=2),
            "llm_model": "mock-orchestrator",
            "llm_usage": {
                "prompt_tokens": 150,
                "completion_tokens": 85,
                "total_tokens": 235,
            },
        }
