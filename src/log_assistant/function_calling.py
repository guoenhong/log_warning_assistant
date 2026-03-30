"""
Function Calling - LLM-driven tool selection using Anthropic SDK
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


# Tool definitions for Anthropic Messages API
TOOL_DEFINITIONS = [
    {
        "name": "analyze_log_stats",
        "description": "Analyze basic log file statistics including total entries, status code distribution, IP distribution, and time range. Use this for any general log analysis question.",
        "input_schema": {
            "type": "object",
            "properties": {
                "log_path": {"type": "string", "description": "Path to the log file"},
                "time_range": {
                    "type": "object",
                    "properties": {
                        "start": {"type": "string", "description": "Start time in ISO format"},
                        "end": {"type": "string", "description": "End time in ISO format"}
                    },
                    "description": "Optional time range filter"
                },
                "top_n": {"type": "integer", "description": "Number of top items to return", "default": 10}
            },
            "required": ["log_path"]
        }
    },
    {
        "name": "analyze_5xx_errors",
        "description": "Analyze 5xx server errors in detail, including status code distribution, top error IPs, and error paths. Use this when user asks about server errors, 5xx, failures, or system issues.",
        "input_schema": {
            "type": "object",
            "properties": {
                "log_path": {"type": "string", "description": "Path to the log file"},
                "time_range": {
                    "type": "object",
                    "properties": {
                        "start": {"type": "string"},
                        "end": {"type": "string"}
                    }
                },
                "top_n": {"type": "integer", "description": "Number of top items to return", "default": 10}
            },
            "required": ["log_path"]
        }
    },
    {
        "name": "search_error_patterns",
        "description": "Search for error patterns in log file using regex patterns like 'error', 'exception', 'timeout', '500', 'failed', etc. Use this when user wants to find specific error messages or patterns.",
        "input_schema": {
            "type": "object",
            "properties": {
                "log_path": {"type": "string", "description": "Path to the log file"},
                "patterns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of regex patterns to search for"
                },
                "time_range": {
                    "type": "object",
                    "properties": {
                        "start": {"type": "string"},
                        "end": {"type": "string"}
                    }
                },
                "top_n": {"type": "integer", "description": "Maximum number of matches to return", "default": 20}
            },
            "required": ["log_path"]
        }
    },
    {
        "name": "search_keywords",
        "description": "Search for specific keywords in log file. Use this when user provides specific keywords or wants to find entries containing specific terms.",
        "input_schema": {
            "type": "object",
            "properties": {
                "log_path": {"type": "string", "description": "Path to the log file"},
                "keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of keywords to search for"
                },
                "time_range": {
                    "type": "object",
                    "properties": {
                        "start": {"type": "string"},
                        "end": {"type": "string"}
                    }
                },
                "top_n": {"type": "integer", "description": "Maximum number of matches to return", "default": 50}
            },
            "required": ["log_path", "keywords"]
        }
    },
    {
        "name": "analyze_404_errors",
        "description": "Analyze 404 Not Found errors in detail, showing which URLs are most frequently missing. Use this when user asks about 404 errors or broken links.",
        "input_schema": {
            "type": "object",
            "properties": {
                "log_path": {"type": "string", "description": "Path to the log file"},
                "time_range": {
                    "type": "object",
                    "properties": {
                        "start": {"type": "string"},
                        "end": {"type": "string"}
                    }
                },
                "top_n": {"type": "integer", "description": "Number of top items to return", "default": 10}
            },
            "required": ["log_path"]
        }
    },
    {
        "name": "analyze_response_time",
        "description": "Analyze slow requests and response time patterns. Use this when user asks about slow requests, performance issues, or response times.",
        "input_schema": {
            "type": "object",
            "properties": {
                "log_path": {"type": "string", "description": "Path to the log file"},
                "time_range": {
                    "type": "object",
                    "properties": {
                        "start": {"type": "string"},
                        "end": {"type": "string"}
                    }
                },
                "top_n": {"type": "integer", "description": "Number of top slow requests to return", "default": 10}
            },
            "required": ["log_path"]
        }
    }
]


# Tool implementations
def execute_tool(tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a tool with given parameters"""
    from tools.log_tools import (
        analyze_log_stats, search_error_patterns, search_keywords, analyze_5xx_errors
    )
    
    tool_map = {
        "analyze_log_stats": lambda: analyze_log_stats(
            parameters.get('log_path'),
            parameters.get('time_range'),
            parameters.get('top_n', 10)
        ),
        "analyze_5xx_errors": lambda: analyze_5xx_errors(
            parameters.get('log_path'),
            parameters.get('time_range'),
            parameters.get('top_n', 10)
        ),
        "search_error_patterns": lambda: search_error_patterns(
            parameters.get('log_path'),
            parameters.get('patterns'),
            parameters.get('time_range'),
            parameters.get('top_n', 20)
        ),
        "search_keywords": lambda: search_keywords(
            parameters.get('log_path'),
            parameters.get('keywords', []),
            parameters.get('time_range'),
            parameters.get('top_n', 50)
        ),
        "analyze_404_errors": lambda: _analyze_404_errors(
            parameters.get('log_path'),
            parameters.get('time_range'),
            parameters.get('top_n', 10)
        ),
        "analyze_response_time": lambda: _analyze_response_time(
            parameters.get('log_path'),
            parameters.get('time_range'),
            parameters.get('top_n', 10)
        ),
    }
    
    if tool_name not in tool_map:
        return {"success": False, "error": f"Unknown tool: {tool_name}"}
    
    try:
        result = tool_map[tool_name]()
        return result.to_dict() if hasattr(result, 'to_dict') else {"success": True, "data": result}
    except Exception as e:
        logger.error(f"Error executing tool {tool_name}: {e}")
        return {"success": False, "error": str(e)}


def _analyze_404_errors(log_path: str, time_range: Optional[Dict] = None, top_n: int = 10) -> Dict:
    """Analyze 404 errors"""
    from src.log_assistant.log_parser import LogParser
    from collections import Counter
    
    parser = LogParser()
    entries = parser.parse_file(log_path)
    
    if time_range:
        start = datetime.fromisoformat(time_range['start']) if 'start' in time_range else None
        end = datetime.fromisoformat(time_range['end']) if 'end' in time_range else None
        entries = parser.filter_by_time_range(start, end)
    
    # Filter 404 errors
    errors_404 = [e for e in entries if e.metadata.get('status') == 404]
    
    if not errors_404:
        return {"success": True, "data": {"message": "No 404 errors found"}}
    
    # Count paths
    paths = [e.message for e in errors_404]
    ips = [e.metadata.get('ip') for e in errors_404 if e.metadata.get('ip')]
    
    return {
        "success": True,
        "data": {
            "total_404": len(errors_404),
            "top_paths": dict(Counter(paths).most_common(top_n)),
            "top_ips": dict(Counter(ips).most_common(top_n)),
            "time_range": _get_time_range(entries)
        }
    }


def _analyze_response_time(log_path: str, time_range: Optional[Dict] = None, top_n: int = 10) -> Dict:
    """Analyze slow requests"""
    from src.log_assistant.log_parser import LogParser
    from collections import Counter
    
    parser = LogParser()
    entries = parser.parse_file(log_path)
    
    if time_range:
        start = datetime.fromisoformat(time_range['start']) if 'start' in time_range else None
        end = datetime.fromisoformat(time_range['end']) if 'end' in time_range else None
        entries = parser.filter_by_time_range(start, end)
    
    # Get entries with time_taken
    slow_entries = [(e, e.metadata.get('time_taken', 0)) for e in entries if e.metadata.get('time_taken', 0) > 0]
    slow_entries.sort(key=lambda x: x[1], reverse=True)
    
    result = []
    for entry, time_taken in slow_entries[:top_n]:
        result.append({
            "timestamp": entry.timestamp.isoformat() if entry.timestamp else None,
            "time_taken_ms": time_taken,
            "message": entry.message,
            "ip": entry.metadata.get('ip'),
            "status": entry.metadata.get('status')
        })
    
    return {
        "success": True,
        "data": {
            "total_slow_requests": len(slow_entries),
            "slowest_requests": result,
            "time_range": _get_time_range(entries)
        }
    }


def _get_time_range(entries):
    timestamps = [e.timestamp for e in entries if e.timestamp]
    if not timestamps:
        return None
    return {
        "start": min(timestamps).isoformat(),
        "end": max(timestamps).isoformat()
    }
