"""
Main Assistant Orchestrator
Coordinates tool selection, execution, and LLM result generation
Two-step approach: LLM decides tools -> execute -> LLM analyzes
"""

import logging
import json
import re
from typing import Dict, Any, List, Optional

from .llm_client import LLMClient
from .output_generator import OutputGenerator
from .call_logger import CallLogger

logger = logging.getLogger(__name__)


class LogAssistantOrchestrator:
    """
    Main orchestrator for log warning assistant
    Uses LLM to decide which tools to use, then executes them
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
        
        Two-step process:
        1. Ask LLM which tools to use
        2. Execute tools and ask LLM to analyze results
        """
        call_id = self.call_logger.start_call()
        
        try:
            # Step 1: Let LLM decide which tools to use
            tools_to_run = self._llm_select_tools(user_question, log_path, time_range, keywords)
            self.call_logger.log_tool_selection(call_id, tools_to_run)
            
            # Step 2: Execute selected tools
            tool_results = self._execute_tools(tools_to_run, log_path, time_range, keywords, top_n)
            
            # Log tool results - create a simple object with success attribute
            for tr in tool_results:
                # Create a simple result object for logging
                class Result:
                    def __init__(self, d):
                        self.success = d.get('success', False)
                        self.data = d.get('data')
                        self.error = d.get('error')
                self.call_logger.log_tool_result(call_id, tr['tool'], Result(tr))
            
            # Step 3: Generate final analysis from tool results
            llm_response = self._generate_analysis(user_question, tool_results, knowledge_text)
            self.call_logger.log_llm_request(call_id, llm_response)
            
            # Build context for output generator
            context = [{
                "tool": tr['tool'],
                "success": tr.get('success', False),
                "data": tr.get('data'),
                "error": tr.get('error')
            } for tr in tool_results]
            
            # Generate structured output
            structured_output = self.output_generator.generate(
                user_question=user_question,
                llm_response={"success": llm_response.get('success', False), "text": llm_response.get('text', '')},
                tool_results=context,
                log_path=log_path,
                time_range=time_range
            )

            # Save report to reports directory
            report_path = self._save_report(log_path, structured_output.get('markdown', ''))
            if report_path:
                logger.info(f"Report saved to: {report_path}")
                structured_output['report_path'] = report_path

            self.call_logger.complete_call(call_id, success=True)

            return {
                "success": True,
                "call_id": call_id,
                "structured_output": structured_output,
                "llm_raw_response": llm_response.get('text'),
                "tools_used": tools_to_run,
                "tool_results": tool_results,
                "report_path": report_path if report_path else None
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
    
    def _llm_select_tools(self, question: str, log_path: str,
                         time_range: Optional[Dict], keywords: Optional[List[str]]) -> List[str]:
        """Ask LLM to decide which tools to use"""
        
        system_prompt = """你是一个日志分析助手。用户的提问决定了需要使用哪些工具。

请根据用户问题，从以下工具列表中选择需要调用的工具：
1. analyze_log_stats - 分析日志基本统计（总是有用）
2. analyze_5xx_errors - 分析5xx服务器错误（用户问5xx/服务器错误/失败时使用）
3. search_error_patterns - 搜索错误模式（用户想找错误/异常时使用）
4. search_keywords - 搜索特定关键词（用户提供关键词时使用）
5. analyze_404_errors - 分析404错误（用户问404/不存在时使用）
6. analyze_response_time - 分析响应时间（用户问慢/性能时使用）

请以JSON数组格式返回工具名称，例如：["analyze_log_stats", "analyze_5xx_errors"]

注意：只返回JSON数组，不要有其他文字。"""
        
        user_prompt = f"""用户问题: {question}
日志文件: {log_path}
时间范围: {time_range}
关键词: {keywords}

请选择需要调用的工具。"""
        
        response = self.llm_client.chat(system_prompt, user_prompt)
        
        if not response.get('success'):
            logger.warning(f"LLM tool selection failed: {response.get('error')}")
            return ["analyze_log_stats"]
        
        text = response.get('text', '')
        try:
            tools = json.loads(text.strip())
            if isinstance(tools, list):
                logger.info(f"LLM selected tools: {tools}")
                return tools
        except json.JSONDecodeError:
            match = re.search(r'\[.*?\]', text, re.DOTALL)
            if match:
                try:
                    tools = json.loads(match.group())
                    if isinstance(tools, list):
                        logger.info(f"LLM selected tools: {tools}")
                        return tools
                except:
                    pass
        
        logger.warning(f"Could not parse tool selection from LLM response: {text}")
        return ["analyze_log_stats"]
    
    def _execute_tools(self, tool_names: List[str], log_path: str,
                      time_range: Optional[Dict], keywords: Optional[List[str]], top_n: int) -> List[Dict]:
        """Execute selected tools"""
        from tools.log_tools import (
            analyze_log_stats, search_error_patterns, search_keywords, analyze_5xx_errors
        )
        from .function_calling import _analyze_404_errors, _analyze_response_time
        
        tool_map = {
            "analyze_log_stats": lambda: analyze_log_stats(log_path, time_range, top_n),
            "analyze_5xx_errors": lambda: analyze_5xx_errors(log_path, time_range, top_n),
            "search_error_patterns": lambda: search_error_patterns(log_path, None, time_range, top_n),
            "search_keywords": lambda: search_keywords(log_path, keywords or [], time_range, top_n),
            "analyze_404_errors": lambda: _analyze_404_errors(log_path, time_range, top_n),
            "analyze_response_time": lambda: _analyze_response_time(log_path, time_range, top_n),
        }
        
        results = []
        for tool_name in tool_names:
            if tool_name not in tool_map:
                logger.warning(f"Unknown tool: {tool_name}")
                continue
            
            try:
                logger.info(f"Executing tool: {tool_name}")
                result = tool_map[tool_name]()
                
                # Handle ToolResult object
                if hasattr(result, 'to_dict'):
                    result_dict = result.to_dict()
                # Handle dict result
                elif isinstance(result, dict):
                    result_dict = result
                # Handle other types
                else:
                    result_dict = {"success": True, "data": str(result)}
                
                results.append({
                    "tool": tool_name,
                    **result_dict
                })
                
            except Exception as e:
                logger.error(f"Error executing tool {tool_name}: {e}")
                results.append({
                    "tool": tool_name,
                    "success": False,
                    "error": str(e)
                })
        
        return results
    
    def _generate_analysis(self, question: str, tool_results: List[Dict],
                         knowledge_text: Optional[str] = None) -> Dict[str, Any]:
        """Generate final analysis from tool results"""
        
        context_text = []
        for tr in tool_results:
            tool_name = tr.get('tool', 'unknown')
            success = tr.get('success', False)
            data = tr.get('data')
            error = tr.get('error')
            
            if success:
                context_text.append(f"--- {tool_name} ---\n{json.dumps(data, indent=2, ensure_ascii=False)}")
            else:
                context_text.append(f"--- {tool_name} ---\nError: {error}")
        
        system_prompt = """你是一个日志分析助手，专门帮助用户分析日志文件并诊断问题。

你的职责：
1. 分析工具返回的数据
2. 给出结构化报告
3. 如果信息不足，明确说明缺失什么数据
4. 提供具体的排查建议

输出格式要求：
1. 结论（发生了什么）
2. 关键数据（状态码分布、Top IP、关键时间窗口等）
3. 建议（优先排查步骤）
4. 如果无法得出结论，输出"信息不足"，并给出下一步需要补充的数据项

请基于提供的工具结果进行准确分析，不要编造数据。"""
        
        if knowledge_text:
            system_prompt += f"\n\n参考知识：\n{knowledge_text}"
        
        user_prompt = f"""工具返回的结果：
{chr(10).join(context_text)}

用户问题：{question}

请给出分析报告。"""
        
        return self.llm_client.chat(system_prompt, user_prompt)
    
    def _save_report(self, log_path: str, markdown_content: str) -> Optional[str]:
        """Save report to reports directory"""
        import os
        from datetime import datetime
        
        if not markdown_content:
            return None
        
        # Get project root (src/log_assistant/ -> project root)
        # __file__ is src/log_assistant/orchestrator.py
        # dirname -> src/log_assistant
        # dirname -> src
        # dirname -> project root
        current_dir = os.path.dirname(os.path.abspath(__file__))
        src_dir = os.path.dirname(current_dir)  # src/
        project_root = os.path.dirname(src_dir)  # project root
        
        reports_dir = os.path.join(project_root, 'reports')
        
        # Create reports directory if not exists
        os.makedirs(reports_dir, exist_ok=True)
        
        # Generate filename: {log_filename}_{timestamp}.md
        log_filename = os.path.basename(log_path)
        # Remove extension
        name_without_ext = os.path.splitext(log_filename)[0]
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_filename = f"{name_without_ext}_{timestamp}.md"
        report_path = os.path.join(reports_dir, report_filename)
        
        # Write report
        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            return report_path
        except Exception as e:
            logger.error(f"Failed to save report: {e}")
            return None
