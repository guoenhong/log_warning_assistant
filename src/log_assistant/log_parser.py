"""
Log Parser Module
Supports common log formats: Nginx, Apache, JSON, and custom patterns
"""

import re
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from dateutil import parser as date_parser

logger = logging.getLogger(__name__)


class LogEntry:
    """Single log entry"""
    def __init__(self, timestamp: Optional[datetime], level: Optional[str], 
                 message: str, raw: str, metadata: Optional[Dict] = None):
        self.timestamp = timestamp
        self.level = level
        self.message = message
        self.raw = raw
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "level": self.level,
            "message": self.message,
            "metadata": self.metadata
        }


class LogParser:
    """Parser for various log formats"""
    
    # Nginx/Apache combined log format
    COMBINED_LOG_PATTERN = re.compile(
        r'(?P<ip>\S+) \S+ \S+ \[(?P<timestamp>[^\]]+)\] '
        r'"(?P<method>\S+) (?P<path>\S+) \S+" (?P<status>\d+) (?P<size>\S+)'
    )
    
    # IIS W3C Extended Log Format
    # Fields: date time s-ip cs-method cs-uri-stem cs-uri-query s-port cs-username c-ip cs(User-Agent) sc-status sc-substatus sc-win32-status time-taken
    IIS_LOG_PATTERN = re.compile(
        r'^(?P<date>\d{4}-\d{2}-\d{2})\s+(?P<time>\d{2}:\d{2}:\d{2})\s+'
        r'(?P<s_ip>\S+)\s+(?P<method>\S+)\s+(?P<uri_stem>\S+)\s+(?P<uri_query>\S+|-)\s+'
        r'(?P<port>\d+)\s+(?P<username>\S+|-)\s+(?P<c_ip>\S+)\s+'
        r'(?P<user_agent>.+?)\s+(?P<status>\d+)\s+(?P<substatus>\d+)\s+'
        r'(?P<win32_status>\d+)\s+(?P<time_taken>\d+)$'
    )
    
    # Simple timestamp + level + message pattern
    SIMPLE_PATTERN = re.compile(
        r'(?P<timestamp>\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}[^\s]*)\s*'
        r'(?P<level>\w+)\s*'
        r'(?P<message>.*)'
    )
    
    # JSON log pattern
    JSON_PATTERN = re.compile(r'^\s*\{.*\}\s*$')
    
    # Comment lines (IIS header)
    COMMENT_PATTERN = re.compile(r'^\s*#')

    def __init__(self, format_type: str = "auto"):
        self.format_type = format_type
        self.entries: List[LogEntry] = []

    def parse_file(self, file_path: str, encoding: str = 'utf-8') -> List[LogEntry]:
        """Parse entire log file"""
        self.entries = []
        
        # Try multiple encodings
        encodings = [encoding, 'gbk', 'gb2312', 'latin-1']
        last_error = None
        
        for enc in encodings:
            self.entries = []
            try:
                with open(file_path, 'r', encoding=enc, errors='ignore') as f:
                    for line_num, line in enumerate(f, 1):
                        line = line.strip()
                        if not line:
                            continue
                        
                        entry = self._parse_line(line, line_num)
                        if entry:
                            self.entries.append(entry)
                logger.info(f"Parsed {len(self.entries)} entries from {file_path} (encoding: {enc})")
                return self.entries
                    
            except FileNotFoundError:
                logger.error(f"Log file not found: {file_path}")
                raise
            except Exception as e:
                last_error = e
                continue
        
        logger.error(f"Error parsing log file {file_path}: {last_error}")
        raise last_error

    def _parse_line(self, line: str, line_num: int) -> Optional[LogEntry]:
        """Parse single log line"""
        # Skip comment lines (IIS header lines)
        if self.COMMENT_PATTERN.match(line):
            return None
        
        # Try JSON format first
        if self.JSON_PATTERN.match(line):
            entry = self._parse_json(line)
            if entry:
                return entry
        
        # Try IIS W3C format
        match = self.IIS_LOG_PATTERN.match(line)
        if match:
            return self._parse_iis(match, line)
        
        # Try combined log format
        match = self.COMBINED_LOG_PATTERN.match(line)
        if match:
            return self._parse_combined(match, line)
        
        # Try simple format
        match = self.SIMPLE_PATTERN.match(line)
        if match:
            return self._parse_simple(match, line)
        
        # Fallback: treat as raw message
        return LogEntry(
            timestamp=None,
            level=self._detect_level(line),
            message=line,
            raw=line,
            metadata={"line_num": line_num}
        )

    def _parse_json(self, line: str) -> Optional[LogEntry]:
        """Parse JSON formatted log"""
        try:
            data = json.loads(line)
            timestamp = None
            if 'timestamp' in data:
                timestamp = date_parser.parse(data['timestamp'])
            elif 'time' in data:
                timestamp = date_parser.parse(data['time'])
            elif '@timestamp' in data:
                timestamp = date_parser.parse(data['@timestamp'])
                
            level = data.get('level', data.get('severity', 'INFO'))
            message = data.get('message', data.get('msg', str(data)))
            
            return LogEntry(
                timestamp=timestamp,
                level=level.upper(),
                message=message,
                raw=line,
                metadata=data
            )
        except json.JSONDecodeError:
            return None

    def _parse_combined(self, match: re.Match, raw: str) -> LogEntry:
        """Parse Nginx/Apache combined log"""
        groups = match.groupdict()
        
        timestamp = None
        if 'timestamp' in groups:
            try:
                timestamp_str = groups['timestamp'].replace('/', ' ').replace(':', ' ', 1)
                timestamp = datetime.strptime(timestamp_str, '%d %b %Y %H:%M:%S')
            except ValueError:
                pass
        
        status = int(groups.get('status', 0))
        level = self._http_status_to_level(status)
        
        return LogEntry(
            timestamp=timestamp,
            level=level,
            message=f"{groups.get('method', '')} {groups.get('path', '')}",
            raw=raw,
            metadata={
                "ip": groups.get('ip'),
                "status": status,
                "size": groups.get('size')
            }
        )
    
    def _parse_iis(self, match: re.Match, raw: str) -> LogEntry:
        """Parse IIS W3C Extended Log Format"""
        groups = match.groupdict()
        
        # Parse timestamp
        timestamp = None
        try:
            date_str = groups.get('date', '')
            time_str = groups.get('time', '')
            if date_str and time_str:
                timestamp = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
        
        # Get HTTP status code
        status = int(groups.get('status', 0))
        level = self._http_status_to_level(status)
        
        # Get method and URI
        method = groups.get('method', '')
        uri_stem = groups.get('uri_stem', '')
        message = f"{method} {uri_stem}"
        
        return LogEntry(
            timestamp=timestamp,
            level=level,
            message=message,
            raw=raw,
            metadata={
                "ip": groups.get('c_ip'),
                "status": status,
                "substatus": int(groups.get('substatus', 0)),
                "win32_status": int(groups.get('win32_status', 0)),
                "time_taken": int(groups.get('time_taken', 0)),
                "uri_query": groups.get('uri_query'),
                "user_agent": groups.get('user_agent', '')[:200],  # Truncate long UA
                "port": int(groups.get('port', 0)),
                "s_ip": groups.get('s_ip'),
                "username": groups.get('username')
            }
        )

    def _parse_simple(self, match: re.Match, raw: str) -> LogEntry:
        """Parse simple timestamp + level + message format"""
        groups = match.groupdict()
        
        timestamp = None
        if groups.get('timestamp'):
            try:
                timestamp = date_parser.parse(groups['timestamp'])
            except:
                pass
        
        return LogEntry(
            timestamp=timestamp,
            level=groups.get('level', 'INFO').upper(),
            message=groups.get('message', ''),
            raw=raw,
            metadata={}
        )

    def _http_status_to_level(self, status: int) -> str:
        """Convert HTTP status code to log level"""
        if status >= 500:
            return "ERROR"
        elif status >= 400:
            return "WARNING"
        elif status >= 300:
            return "INFO"
        else:
            return "INFO"

    def _detect_level(self, message: str) -> str:
        """Detect log level from message content"""
        message_upper = message.upper()
        if any(w in message_upper for w in ['ERROR', 'FATAL', 'CRITICAL']):
            return "ERROR"
        elif any(w in message_upper for w in ['WARN', 'WARNING']):
            return "WARNING"
        elif any(w in message_upper for w in ['DEBUG']):
            return "DEBUG"
        return "INFO"

    def filter_by_time_range(self, start: Optional[datetime] = None, 
                            end: Optional[datetime] = None) -> List[LogEntry]:
        """Filter entries by time range"""
        if not start and not end:
            return self.entries
            
        filtered = []
        for entry in self.entries:
            if entry.timestamp is None:
                continue
            if start and entry.timestamp < start:
                continue
            if end and entry.timestamp > end:
                continue
            filtered.append(entry)
        return filtered

    def filter_by_level(self, levels: List[str]) -> List[LogEntry]:
        """Filter entries by log level"""
        levels_upper = [l.upper() for l in levels]
        return [e for e in self.entries if e.level and e.level.upper() in levels_upper]

    def filter_by_keyword(self, keyword: str) -> List[LogEntry]:
        """Filter entries containing keyword"""
        return [e for e in self.entries if keyword.lower() in e.message.lower()]
