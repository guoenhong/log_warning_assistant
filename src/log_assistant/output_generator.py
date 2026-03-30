"""
Output Generator
Generates structured output based on LLM response and tool results
"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class OutputGenerator:
    """Generate structured output in fixed format"""
    
    def generate(self, user_question: str, llm_response: Dict[str, Any],
                tool_results: List[Dict[str, Any]], log_path: str,
                time_range: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Generate structured output
        
        Returns:
            Dict with: conclusion, key_data, suggestions, info_status
        """
        # Check if LLM response is successful
        if not llm_response.get('success'):
            return self.generate_error(llm_response.get('error', 'LLM request failed'))
        
        llm_text = llm_response.get('text', '')
        
        # Parse structured data from tool results
        structured_data = self._extract_structured_data(tool_results)
        
        # Build output
        output = {
            "question": user_question,
            "log_file": log_path,
            "time_range": time_range,
            "analysis": {
                "conclusion": self._extract_conclusion(llm_text),
                "key_data": structured_data,
                "suggestions": self._extract_suggestions(llm_text),
            },
            "info_status": self._check_info_sufficient(llm_text),
            "raw_llm_response": llm_text
        }
        
        # Format as markdown
        output["markdown"] = self._format_markdown(output)
        
        return output
    
    def _extract_structured_data(self, tool_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract key data from tool results"""
        data = {}
        
        for result in tool_results:
            if not result.get('success'):
                continue
                
            tool_data = result.get('data', {})
            tool_name = result.get('tool', 'unknown')
            
            if tool_name == 'analyze_log_stats':
                data['log_stats'] = {
                    'total_entries': tool_data.get('total_entries'),
                    'level_distribution': tool_data.get('level_distribution'),
                    'status_distribution': tool_data.get('status_distribution'),
                    'top_ips': tool_data.get('top_ips'),
                    'time_range': tool_data.get('time_range')
                }
            elif tool_name == 'analyze_5xx_errors':
                data['error_5xx'] = {
                    'total': tool_data.get('total_5xx'),
                    'status_distribution': tool_data.get('status_distribution'),
                    'top_ips': tool_data.get('top_ips'),
                    'top_paths': tool_data.get('top_paths')
                }
            elif tool_name == 'search_error_patterns':
                data['error_patterns'] = {
                    'matched_count': tool_data.get('matched_count'),
                    'pattern_frequency': tool_data.get('pattern_frequency')
                }
            elif tool_name == 'search_keywords':
                data['keyword_search'] = {
                    'matched_count': tool_data.get('matched_count'),
                    'keywords': tool_data.get('keywords_searched')
                }
        
        return data
    
    def _extract_conclusion(self, llm_text: str) -> str:
        """Extract conclusion from LLM response"""
        # Look for conclusion section or first paragraph
        lines = llm_text.split('\n')
        conclusion = []
        in_conclusion = False
        
        for line in lines:
            if '结论' in line or '总结' in line:
                in_conclusion = True
                continue
            if in_conclusion and line.strip():
                conclusion.append(line.strip())
            if len(conclusion) > 3:
                break
        
        if conclusion:
            return '\n'.join(conclusion[:3])
        
        # Fallback: first 100 chars
        return llm_text[:200] if len(llm_text) > 200 else llm_text
    
    def _extract_suggestions(self, llm_text: str) -> List[str]:
        """Extract suggestions from LLM response"""
        suggestions = []
        lines = llm_text.split('\n')
        in_suggestion = False
        
        for line in lines:
            if '建议' in line or '排查' in line or '下一步' in line:
                in_suggestion = True
                continue
            if in_suggestion and line.strip():
                if line.strip().startswith(('1', '2', '3', '4', '5', '•', '-', '•')):
                    suggestions.append(line.strip())
        
        return suggestions[:5]  # Max 5 suggestions
    
    def _check_info_sufficient(self, llm_text: str) -> str:
        """Check if information is sufficient"""
        insufficient_keywords = ['信息不足', '无法确定', '没有足够', '缺少数据', '需要更多信息']
        
        if any(kw in llm_text for kw in insufficient_keywords):
            return "insufficient"
        return "sufficient"
    
    def _format_markdown(self, output: Dict[str, Any]) -> str:
        """Format output as markdown"""
        md = []
        
        # Header
        md.append("# 日志分析报告")
        md.append("")
        
        # Question
        md.append(f"**问题**: {output['question']}")
        md.append(f"**日志文件**: {output['log_file']}")
        if output.get('time_range'):
            md.append(f"**时间范围**: {output['time_range'].get('start')} ~ {output['time_range'].get('end')}")
        md.append("")
        
        # Status indicator
        status = output.get('info_status', 'sufficient')
        status_text = "✅ 信息充分" if status == "sufficient" else "⚠️ 信息不足"
        md.append(f"**状态**: {status_text}")
        md.append("")
        
        # Conclusion
        md.append("## 1. 结论")
        md.append(output['analysis']['conclusion'])
        md.append("")
        
        # Key data
        md.append("## 2. 关键数据")
        key_data = output['analysis']['key_data']
        
        if 'log_stats' in key_data:
            stats = key_data['log_stats']
            md.append(f"- 总日志条目: {stats.get('total_entries', 'N/A')}")
            if stats.get('level_distribution'):
                md.append(f"- 日志级别分布: {stats['level_distribution']}")
            if stats.get('time_range'):
                tr = stats['time_range']
                md.append(f"- 日志时间范围: {tr.get('start', 'N/A')} ~ {tr.get('end', 'N/A')}")
        
        if 'error_5xx' in key_data:
            error = key_data['error_5xx']
            md.append(f"- 5xx错误总数: {error.get('total', 'N/A')}")
            if error.get('status_distribution'):
                md.append(f"- 错误状态码分布: {error['status_distribution']}")
            if error.get('top_ips'):
                md.append(f"- Top错误IP: {dict(list(error['top_ips'].items())[:5])}")
        
        if 'error_patterns' in key_data:
            patterns = key_data['error_patterns']
            md.append(f"- 错误模式匹配数: {patterns.get('matched_count', 'N/A')}")
        
        md.append("")
        
        # Suggestions
        suggestions = output['analysis']['suggestions']
        if suggestions:
            md.append("## 3. 建议")
            for s in suggestions:
                md.append(f"- {s}")
            md.append("")
        
        # Info不足时的补充说明
        if status == "insufficient":
            md.append("## 4. 需要补充的数据")
            md.append("请提供以下信息以获得更准确的分析：")
            md.append("- 更精确的时间范围")
            md.append("- 相关的关键词")
            md.append("- 历史故障记录")
        
        return '\n'.join(md)
    
    def generate_error(self, error_msg: str) -> Dict[str, Any]:
        """Generate error output"""
        return {
            "error": True,
            "message": error_msg,
            "markdown": f"# 错误\n\n{error_msg}",
            "info_status": "error"
        }
