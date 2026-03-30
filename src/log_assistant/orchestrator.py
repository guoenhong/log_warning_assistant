"""
Main Assistant Orchestrator
Coordinates tool selection, execution, and LLM result generation
"""

import logging
from typing import Dict, Any, List, Optional

from .llm_client import LLMClient
from ..tools.log_tools import (
    analyze_log_stats, search_error_patterns, search_keywords, analyze_5xx_errors
)
from .output_generator import OutputGenerator
from .call_logger import CallLogger

logger = logging.getLogger(__name__)


class LogAssistantOrchestrator:
    """
    Main orchestrator for log warning assistant
    Coordinates tool selection, execution, and LLM response generation
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.llm_client = LLMClient(config.get('llm', {}))
        self.output_generator = OutputGenerator()
        self.call_logger = CallLogger(config.get('call_log', {}))
        
    def process(self, user_question: str, log_path: str, 
                time_range: Optional[Dict[str, str]] = None,
                keywords: Optional[List[str]] = None,
                top_n: int = 10,
                knowledge_text: Optional[str] = None) -> Dict[str, Any]:
        """
        Process user question and generate analysis report
        
        Args:
            user_question: Natural language question
            log_path: Path to log file
            time_range: Optional time range
            keywords: Optional keywords for search
            top_n: Number of top items
            knowledge_text: Optional knowledge text (FAQ, etc.)
            
        Returns:
            Dict with structured output
        """
        call_id = self.call_logger.start_call()
        context = []
        
        try:
            # Step 1: Select appropriate tools based on question
            tools_to_run = self._select_tools(user_question, keywords)
            self.call_logger.log_tool_selection(call_id, tools_to_run)
            
            # Step 2: Execute selected tools
            for tool_name in tools_to_run:
                result = self._execute_tool(
                    tool_name, log_path, time_range, keywords, top_n
                )
                context.append({
                    "tool": tool_name,
                    **result.to_dict()
                })
                self.call_logger.log_tool_result(call_id, tool_name, result)
                
                # Early exit if critical tool fails
                if not result.success:
                    logger.warning(f"Tool {tool_name} failed: {result.error}")
            
            # Step 3: Generate LLM response
            llm_response = self._generate_response(
                user_question, context, knowledge_text
            )
            self.call_logger.log_llm_request(call_id, llm_response)
            
            # Step 4: Generate structured output
            structured_output = self.output_generator.generate(
                user_question=user_question,
                llm_response=llm_response,
                tool_results=context,
                log_path=log_path,
                time_range=time_range
            )
            
            self.call_logger.complete_call(call_id, success=True)
            
            return {
                "success": True,
                "call_id": call_id,
                "structured_output": structured_output,
                "llm_raw_response": llm_response.get('text') if llm_response.get('success') else None,
                "tools_used": tools_to_run
            }
            
        except Exception as e:
            logger.error(f"Error processing request: {e}")
            self.call_logger.complete_call(call_id, success=False, error=str(e))
            return {
                "success": False,
                "call_id": call_id,
                "error": str(e),
                "structured_output": self.output_generator.generate_error(str(e))
            }
    
    def _select_tools(self, question: str, keywords: Optional[List[str]]) -> List[str]:
        """
        Select appropriate tools based on user question
        
        Returns list of tool names to execute
        """
        question_lower = question.lower()
        tools = []
        
        # Always run basic stats
        tools.append("analyze_log_stats")
        
        # Check for 5xx / error related questions
        if any(kw in question_lower for kw in ['5xx', '500', '501', '502', '503', '异常', 
                                               '错误', 'error', '失败', '升高', 'increase']):
            tools.append("analyze_5xx_errors")
            tools.append("search_error_patterns")
        
        # Check for specific keywords
        if keywords:
            tools.append("search_keywords")
        
        # General error pattern search
        if any(kw in question_lower for kw in ['error', 'exception', '异常', '错误', '故障']):
            tools.append("search_error_patterns")
        
        # Remove duplicates while preserving order
        seen = set()
        unique_tools = []
        for t in tools:
            if t not in seen:
                seen.add(t)
                unique_tools.append(t)
                
        logger.info(f"Selected tools: {unique_tools}")
        return unique_tools
    
    def _execute_tool(self, tool_name: str, log_path: str, 
                     time_range: Optional[Dict[str, str]],
                     keywords: Optional[List[str]], top_n: int):
        """Execute a single tool"""
        logger.info(f"Executing tool: {tool_name}")
        
        tool_map = {
            "analyze_log_stats": lambda: analyze_log_stats(log_path, time_range, top_n),
            "search_error_patterns": lambda: search_error_patterns(log_path, None, time_range, top_n),
            "search_keywords": lambda: search_keywords(log_path, keywords or [], time_range, top_n),
            "analyze_5xx_errors": lambda: analyze_5xx_errors(log_path, time_range, top_n),
        }
        
        tool_func = tool_map.get(tool_name)
        if not tool_func:
            from .log_tools import ToolResult
            return ToolResult(success=False, error=f"Unknown tool: {tool_name}")
        
        return tool_func()
    
    def _generate_response(self, question: str, context: List[Dict[str, Any]], 
                          knowledge_text: Optional[str]) -> Dict[str, Any]:
        """Generate LLM response based on tool results"""
        
        system_prompt = """你是一个日志分析助手，专门帮助用户分析日志文件并诊断问题。
你的职责：
1. 根据用户问题选择合适的工具进行分析
2. 分析工具返回的数据，给出结构化报告
3. 如果信息不足，明确说明缺失什么数据
4. 提供具体的排查建议

输出格式要求：
1. 结论（发生了什么）
2. 关键数据（状态码分布、Top IP、关键时间窗口等）
3. 建议（优先排查步骤）
4. 如果无法得出结论，输出"信息不足"，并给出下一步需要补充的数据项

请基于提供的工具结果进行准确分析，不要编造数据。"""
        
        # Add knowledge text if provided
        if knowledge_text:
            system_prompt += f"\n\n参考知识：\n{knowledge_text}"
        
        return self.llm_client.chat_with_context(
            system_prompt=system_prompt,
            user_prompt=question,
            context=context
        )
