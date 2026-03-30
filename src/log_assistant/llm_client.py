"""
LLM Client - MiniMax M2.7 Integration
"""

import os
import logging
from typing import Dict, Any, List, Optional

try:
    from openai import OpenAI
except ImportError:
    raise ImportError("Please install openai: pip install openai")

logger = logging.getLogger(__name__)


class LLMClient:
    """MiniMax M2.7 LLM client (OpenAI-compatible API)"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        api_key = os.environ.get('MINIMAX_API_KEY', config.get('api_key', ''))
        base_url = config.get('base_url', 'https://api.minimax.chat/v1')
        
        if not api_key:
            raise ValueError("MINIMAX_API_KEY environment variable not set")
        
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        self.model = config.get('model', 'MiniMax-M2.7')
        self.temperature = config.get('temperature', 0.7)
        self.max_tokens = config.get('max_tokens', 2000)
        
    def chat(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """
        Send chat request to LLM
        
        Args:
            system_prompt: System prompt
            user_prompt: User prompt
            
        Returns:
            Response dict with text and metadata
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            result = {
                "success": True,
                "text": response.choices[0].message.content,
                "model": response.model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            }
            
            logger.info(f"LLM request successful: {result['usage']['total_tokens']} tokens")
            return result
            
        except Exception as e:
            logger.error(f"LLM request failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "text": None
            }
    
    def chat_with_context(self, system_prompt: str, user_prompt: str, 
                          context: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Send chat request with context from tools
        
        Args:
            system_prompt: System prompt
            user_prompt: User prompt
            context: List of tool results as context
            
        Returns:
            Response dict
        """
        # Build context from tool results
        context_text = self._format_context(context)
        
        full_prompt = f"""Context from log analysis tools:
{context_text}

User question: {user_prompt}

Please provide a structured analysis based on the above context. 
If the context doesn't contain enough information to answer the question, 
clearly state "信息不足" and specify what additional data is needed."""
        
        return self.chat(system_prompt, full_prompt)
    
    def _format_context(self, context: List[Dict[str, Any]]) -> str:
        """Format tool results as context"""
        lines = []
        for i, ctx in enumerate(context, 1):
            tool_name = ctx.get('tool', f'tool_{i}')
            success = ctx.get('success', False)
            data = ctx.get('data')
            error = ctx.get('error')
            
            lines.append(f"--- Tool: {tool_name} ---")
            if success:
                lines.append(f"Result: {self._format_data(data)}")
            else:
                lines.append(f"Error: {error}")
            lines.append("")
        
        return "\n".join(lines)
    
    def _format_data(self, data: Any, max_length: int = 2000) -> str:
        """Format data for context (truncate if too long)"""
        import json
        text = json.dumps(data, indent=2, ensure_ascii=False)
        if len(text) > max_length:
            text = text[:max_length] + "...[truncated]"
        return text
