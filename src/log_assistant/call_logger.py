"""
Call Logger
Records tool calls, parameters, and success status
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class CallLogger:
    """Logger for tracking tool calls and LLM requests"""
    
    def __init__(self, config: Dict[str, Any]):
        self.enabled = config.get('enabled', True)
        log_file = config.get('log_file', 'logs/calls.log')
        
        # Ensure directory exists
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        
        self.log_file = log_file
        self.current_call: Optional[Dict[str, Any]] = None
        
    def start_call(self) -> str:
        """Start a new call session"""
        call_id = str(uuid.uuid4())[:8]
        self.current_call = {
            "call_id": call_id,
            "start_time": datetime.now().isoformat(),
            "tools": [],
            "llm_requests": []
        }
        logger.info(f"Started call: {call_id}")
        return call_id
    
    def log_tool_selection(self, call_id: str, tools: list):
        """Log selected tools"""
        if not self.enabled or not self.current_call:
            return
            
        self.current_call["selected_tools"] = tools
        logger.info(f"Call {call_id}: Selected tools: {tools}")
    
    def log_tool_result(self, call_id: str, tool_name: str, result: Any):
        """Log tool execution result"""
        if not self.enabled or not self.current_call:
            return
            
        tool_log = {
            "tool": tool_name,
            "success": result.success,
            "timestamp": datetime.now().isoformat()
        }
        
        if result.success:
            tool_log["data_summary"] = self._summarize_data(result.data)
        else:
            tool_log["error"] = result.error
            
        self.current_call["tools"].append(tool_log)
        logger.info(f"Call {call_id}: Tool {tool_name} - {'success' if result.success else 'failed'}")
    
    def log_llm_request(self, call_id: str, response: Dict[str, Any]):
        """Log LLM request and response"""
        if not self.enabled or not self.current_call:
            return
            
        llm_log = {
            "timestamp": datetime.now().isoformat(),
            "success": response.get('success', False),
            "usage": response.get('usage', {})
        }
        
        if not response.get('success'):
            llm_log["error"] = response.get('error')
        else:
            # Only store first 500 chars of response
            text = response.get('text', '')
            llm_log["response_preview"] = text[:500] if text else None
            
        self.current_call["llm_requests"].append(llm_log)
        logger.info(f"Call {call_id}: LLM request - {'success' if response.get('success') else 'failed'}")
    
    def complete_call(self, call_id: str, success: bool, error: Optional[str] = None):
        """Complete and save call log"""
        if not self.enabled or not self.current_call:
            return
            
        self.current_call["end_time"] = datetime.now().isoformat()
        self.current_call["success"] = success
        if error:
            self.current_call["error"] = error
            
        # Write to file
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(self.current_call, ensure_ascii=False) + '\n')
        except Exception as e:
            logger.error(f"Failed to write call log: {e}")
            
        logger.info(f"Call {call_id}: Completed - {'success' if success else 'failed'}")
        self.current_call = None
    
    def _summarize_data(self, data: Any, max_len: int = 200) -> str:
        """Create summary of data for logging"""
        if data is None:
            return "None"
        if isinstance(data, dict):
            keys = list(data.keys())[:5]
            return f"dict(keys={keys})"
        if isinstance(data, (list, tuple)):
            return f"list(len={len(data)})"
        if isinstance(data, str):
            return data[:max_len] if len(data) > max_len else data
        return str(type(data))
