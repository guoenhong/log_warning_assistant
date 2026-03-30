"""
LLM Client - MiniMax M2.7 Integration
"""

import os
import logging
from typing import Dict, Any, List, Optional

try:
    import anthropic
except ImportError:
    raise ImportError("Please install anthropic: pip install anthropic")

logger = logging.getLogger(__name__)

# Try to load .env file
try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
    load_dotenv(env_path)
except ImportError:
    pass


class LLMClient:
    """MiniMax M2.7 LLM client using Anthropic SDK"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # 优先级: config > ANTHROPIC_API_KEY > MINIMAX_API_KEY
        api_key = (
            config.get('api_key') or 
            os.environ.get('ANTHROPIC_API_KEY', '') or 
            os.environ.get('MINIMAX_API_KEY', '')
        )
        
        # base_url: config > ANTHROPIC_BASE_URL
        base_url = config.get('base_url') or os.environ.get('ANTHROPIC_BASE_URL', '')
        
        if not api_key:
            raise ValueError(
                "请在 config/config.yaml 中设置 api_key，或在 .env 中设置 ANTHROPIC_API_KEY"
            )
        
        # Initialize client with custom base_url if provided
        if base_url:
            self.client = anthropic.Anthropic(
                api_key=api_key,
                base_url=base_url
            )
            logger.info(f"Using custom base_url: {base_url}")
        else:
            self.client = anthropic.Anthropic(api_key=api_key)
        
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
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": user_prompt
                            }
                        ]
                    }
                ],
                temperature=self.temperature
            )
            
            # Extract text content
            text_content = ""
            thinking_content = ""
            for block in response.content:
                if block.type == "text":
                    text_content += block.text
                elif block.type == "thinking":
                    thinking_content += block.thinking
            
            result = {
                "success": True,
                "text": text_content,
                "thinking": thinking_content if thinking_content else None,
                "model": response.model,
                "usage": {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens
                }
            }
            
            logger.info(f"LLM request successful: {result['usage']['output_tokens']} output tokens")
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

    def chat_with_tools(self, system_prompt: str, user_prompt: str,
                       tools: List[Dict], max_tool_calls: int = 5) -> Dict[str, Any]:
        """
        Send chat request with tools, allowing LLM to decide which tools to call.
        
        Args:
            system_prompt: System prompt
            user_prompt: User question
            tools: List of tool definitions
            max_tool_calls: Maximum number of tool calls allowed
            
        Returns:
            Dict with: text, tool_calls, tool_results
        """
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": user_prompt
                    }
                ]
            }
        ]
        
        try:
            # First call - let LLM decide which tools to use
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system_prompt,
                messages=messages,
                tools=tools,
                temperature=self.temperature
            )
            
            # Collect tool use requests
            tool_calls = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_calls.append({
                        "id": block.id,
                        "name": block.name,
                        "input": block.input
                    })
            
            # If no tool calls, return the text response
            if not tool_calls:
                text_content = ""
                for block in response.content:
                    if block.type == "text":
                        text_content += block.text
                
                return {
                    "success": True,
                    "text": text_content,
                    "tool_calls": [],
                    "tool_results": [],
                    "usage": {
                        "input_tokens": response.usage.input_tokens,
                        "output_tokens": response.usage.output_tokens
                    }
                }
            
            # Execute tool calls and collect results
            from .function_calling import execute_tool
            
            tool_results = []
            for tool_call in tool_calls[:max_tool_calls]:
                tool_name = tool_call['name']
                tool_params = tool_call['input']
                
                logger.info(f"LLM requested tool: {tool_name}")
                result = execute_tool(tool_name, tool_params)
                
                tool_results.append({
                    "tool_call_id": tool_call['id'],
                    "tool_name": tool_name,
                    "result": result
                })
            
            # Build assistant message with tool results
            assistant_content = []
            for tc in tool_calls[:max_tool_calls]:
                assistant_content.append({
                    "type": "tool_use",
                    "id": tc['id'],
                    "name": tc['name'],
                    "input": tc['input']
                })
            
            # Add tool results as user message (MiniMax compatible format)
            tool_result_text = []
            for tr in tool_results:
                tool_result_text.append(
                    f"Tool '{tr['tool_name']}' returned: {self._format_tool_result(tr['result'])}"
                )
            
            # Add assistant message with tool use
            messages.append({
                "role": "assistant",
                "content": assistant_content
            })
            
            # Add tool results as user message
            messages.append({
                "role": "user",
                "content": "\n\n".join(tool_result_text) + "\n\n请基于以上工具返回的结果，给出最终的分析报告。"
            })
            
            response2 = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system_prompt,
                messages=messages,
                temperature=self.temperature
            )
            
            # Extract final text
            text_content = ""
            for block in response2.content:
                if block.type == "text":
                    text_content += block.text
            
            return {
                "success": True,
                "text": text_content,
                "tool_calls": tool_calls,
                "tool_results": tool_results,
                "usage": {
                    "input_tokens": response.usage.input_tokens + response2.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens + response2.usage.output_tokens
                }
            }
            
        except Exception as e:
            logger.error(f"Tool calling failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "text": None,
                "tool_calls": [],
                "tool_results": []
            }
    
    def _format_tool_result(self, result: Dict) -> str:
        """Format tool result for LLM"""
        import json
        if result.get('success'):
            data = result.get('data', {})
            return json.dumps(data, indent=2, ensure_ascii=False)
        else:
            return f"Error: {result.get('error', 'Unknown error')}"
