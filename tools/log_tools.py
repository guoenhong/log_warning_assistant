"""
Tool Functions for Log Analysis
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import Counter, defaultdict
import re

from ..log_assistant.log_parser import LogParser, LogEntry

logger = logging.getLogger(__name__)


class ToolResult:
    """Result from tool execution"""
    def __init__(self, success: bool, data: Any = None, error: str = None):
        self.success = success
        self.data = data
        self.error = error
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error
        }


def analyze_log_stats(log_path: str, time_range: Optional[Dict[str, str]] = None,
                     top_n: int = 10) -> ToolResult:
    """
    Analyze log file statistics
    
    Args:
        log_path: Path to log file
        time_range: Optional time range {"start": "ISO date", "end": "ISO date"}
        top_n: Number of top items to return
    
    Returns:
        ToolResult with statistics
    """
    try:
        parser = LogParser()
        entries = parser.parse_file(log_path)
        
        # Apply time filter if specified
        if time_range:
            start = datetime.fromisoformat(time_range['start']) if 'start' in time_range else None
            end = datetime.fromisoformat(time_range['end']) if 'end' in time_range else None
            entries = parser.filter_by_time_range(start, end)
        
        if not entries:
            return ToolResult(success=True, data={"message": "No log entries found"})
        
        # Calculate statistics
        stats = {
            "total_entries": len(entries),
            "level_distribution": _count_levels(entries),
            "status_distribution": _count_status(entries),
            "top_ips": _get_top_ips(entries, top_n),
            "time_range": _get_time_range(entries)
        }
        
        logger.info(f"Log stats analysis complete: {stats['total_entries']} entries")
        return ToolResult(success=True, data=stats)
        
    except Exception as e:
        logger.error(f"Error analyzing log stats: {e}")
        return ToolResult(success=False, error=str(e))


def search_error_patterns(log_path: str, patterns: Optional[List[str]] = None,
                          time_range: Optional[Dict[str, str]] = None,
                          top_n: int = 20) -> ToolResult:
    """
    Search for error patterns in log file
    
    Args:
        log_path: Path to log file
        patterns: List of regex patterns to search
        time_range: Optional time range
        top_n: Maximum number of matches to return
    
    Returns:
        ToolResult with matched error entries
    """
    try:
        parser = LogParser()
        entries = parser.parse_file(log_path)
        
        # Filter by time
        if time_range:
            start = datetime.fromisoformat(time_range['start']) if 'start' in time_range else None
            end = datetime.fromisoformat(time_range['end']) if 'end' in time_range else None
            entries = parser.filter_by_time_range(start, end)
        
        # Default error patterns
        if not patterns:
            patterns = [
                r'error',
                r'exception',
                r'failed',
                r'timeout',
                r'500\s',
                r'5\d{2}',
                r'fatal',
                r'critical'
            ]
        
        # Search for patterns
        matched_entries = []
        pattern_regexes = [re.compile(p, re.IGNORECASE) for p in patterns]
        
        for entry in entries:
            for regex in pattern_regexes:
                if regex.search(entry.message) or regex.search(entry.raw):
                    matched_entries.append({
                        "timestamp": entry.timestamp.isoformat() if entry.timestamp else None,
                        "level": entry.level,
                        "message": entry.message[:200],  # Truncate long messages
                        "metadata": entry.metadata
                    })
                    break
        
        # Get top patterns
        pattern_counts = _count_patterns(entries, patterns)
        
        result = {
            "matched_count": len(matched_entries),
            "matched_entries": matched_entries[:top_n],
            "pattern_frequency": pattern_counts,
            "time_range": _get_time_range(entries)
        }
        
        logger.info(f"Error pattern search complete: {len(matched_entries)} matches")
        return ToolResult(success=True, data=result)
        
    except Exception as e:
        logger.error(f"Error searching error patterns: {e}")
        return ToolResult(success=False, error=str(e))


def search_keywords(log_path: str, keywords: List[str],
                   time_range: Optional[Dict[str, str]] = None,
                   top_n: int = 50) -> ToolResult:
    """
    Search for specific keywords in log file
    
    Args:
        log_path: Path to log file
        keywords: List of keywords to search
        time_range: Optional time range
        top_n: Maximum number of matches to return
    
    Returns:
        ToolResult with matched entries
    """
    try:
        parser = LogParser()
        entries = parser.parse_file(log_path)
        
        # Filter by time
        if time_range:
            start = datetime.fromisoformat(time_range['start']) if 'start' in time_range else None
            end = datetime.fromisoformat(time_range['end']) if 'end' in time_range else None
            entries = parser.filter_by_time_range(start, end)
        
        # Search for keywords
        matched_entries = []
        for entry in entries:
            for keyword in keywords:
                if keyword.lower() in entry.message.lower():
                    matched_entries.append({
                        "timestamp": entry.timestamp.isoformat() if entry.timestamp else None,
                        "level": entry.level,
                        "message": entry.message[:200],
                        "keyword_matched": keyword,
                        "metadata": entry.metadata
                    })
                    break
        
        result = {
            "matched_count": len(matched_entries),
            "matched_entries": matched_entries[:top_n],
            "keywords_searched": keywords,
            "time_range": _get_time_range(entries)
        }
        
        logger.info(f"Keyword search complete: {len(matched_entries)} matches for {keywords}")
        return ToolResult(success=True, data=result)
        
    except Exception as e:
        logger.error(f"Error searching keywords: {e}")
        return ToolResult(success=False, error=str(e))


def analyze_5xx_errors(log_path: str, time_range: Optional[Dict[str, str]] = None,
                       top_n: int = 10) -> ToolResult:
    """
    Analyze 5xx errors specifically
    
    Args:
        log_path: Path to log file
        time_range: Optional time range
        top_n: Number of top items to return
    
    Returns:
        ToolResult with 5xx error analysis
    """
    try:
        parser = LogParser()
        entries = parser.parse_file(log_path)
        
        # Filter by time
        if time_range:
            start = datetime.fromisoformat(time_range['start']) if 'start' in time_range else None
            end = datetime.fromisoformat(time_range['end']) if 'end' in time_range else None
            entries = parser.filter_by_time_range(start, end)
        
        # Filter 5xx errors
        error_5xx = [e for e in entries if e.metadata.get('status', 0) >= 500]
        
        if not error_5xx:
            return ToolResult(success=True, data={"message": "No 5xx errors found"})
        
        # Analyze patterns
        status_codes = [e.metadata.get('status') for e in error_5xx]
        ips = [e.metadata.get('ip') for e in error_5xx if e.metadata.get('ip')]
        paths = [e.message for e in error_5xx]
        
        result = {
            "total_5xx": len(error_5xx),
            "status_distribution": dict(Counter(status_codes)),
            "top_ips": dict(Counter(ips).most_common(top_n)),
            "top_paths": dict(Counter(paths).most_common(top_n)),
            "time_range": _get_time_range(entries)
        }
        
        logger.info(f"5xx error analysis complete: {len(error_5xx)} errors")
        return ToolResult(success=True, data=result)
        
    except Exception as e:
        logger.error(f"Error analyzing 5xx errors: {e}")
        return ToolResult(success=False, error=str(e))


# Helper functions
def _count_levels(entries: List[LogEntry]) -> Dict[str, int]:
    levels = [e.level for e in entries if e.level]
    return dict(Counter(levels))

def _count_status(entries: List[LogEntry]) -> Dict[int, int]:
    statuses = [e.metadata.get('status') for e in entries if e.metadata.get('status')]
    return {k: v for k, v in Counter(statuses).items() if k}

def _get_top_ips(entries: List[LogEntry], top_n: int) -> Dict[str, int]:
    ips = [e.metadata.get('ip') for e in entries if e.metadata.get('ip')]
    return dict(Counter(ips).most_common(top_n))

def _get_time_range(entries: List[LogEntry]) -> Optional[Dict[str, str]]:
    timestamps = [e.timestamp for e in entries if e.timestamp]
    if not timestamps:
        return None
    return {
        "start": min(timestamps).isoformat(),
        "end": max(timestamps).isoformat()
    }

def _count_patterns(entries: List[LogEntry], patterns: List[str]) -> Dict[str, int]:
    counts = {}
    for pattern in patterns:
        regex = re.compile(pattern, re.IGNORECASE)
        count = sum(1 for e in entries if regex.search(e.message) or regex.search(e.raw))
        counts[pattern] = count
    return counts
