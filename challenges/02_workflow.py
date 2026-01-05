# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "openai",
# ]
# ///

import os
import json
import sys
import time
from openai import OpenAI

# ==========================================
# 配置区域
# ==========================================
API_KEY = os.getenv("DEEPSEEK_API_KEY")
BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
# 允许从环境变量覆盖模型名称，默认为 deepseek-chat
MODEL_NAME = os.getenv("DEEPSEEK_MODEL_NAME", "deepseek-chat")

if not API_KEY:
    print("❌ Error: 请设置环境变量 DEEPSEEK_API_KEY")
    sys.exit(1)

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

class LongArticleAgent:
    def __init__(self, topic):
        self.topic = topic
        self.outline = []
        self.articles = []

    def step1_generate_outline(self):
        """Step 1: 生成章节大纲"""
        print(f"📋 正在规划主题: {self.topic}...")
        
        # TODO: 编写 Prompt 让模型生成纯 JSON 列表
        prompt = f"请为主题《{self.topic}》生成一个包含3个章节的大纲..."+"""
        
        要求：
        1. 输出必须是纯JSON格式，不包含任何Markdown标记或额外解释[2](@ref)
        2. 包含3个主要章节，每个章节包含标题和1-3个关键要点
        3. 章节之间要有逻辑递进关系
        
        严格按照以下JSON格式输出：
        {{
            "outline": [
                {{
                    "title": "章节标题1",
                    "key_points": ["要点1", "要点2", "要点3"]
                }},
                {{
                    "title": "章节标题2", 
                    "key_points": ["要点1"]
                }},
                {{
                    "title": "章节标题3",
                    "key_points": ["要点1", "要点2"]
                }}
            ]
        }}
        
        只输出JSON对象，不要其他任何内容。
        """
        
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,  # 使用配置的模型名
                messages=[
                    {"role": "system", "content": "你是一个专业的写作规划师，只输出 JSON Array。"},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.7
            )
            content = response.choices[0].message.content
            
            # TODO: 解析返回的 JSON 内容到 self.outline
            data = json.loads(content)
            
            # 简单的容错逻辑示例（候选人需要完善）
            # if isinstance(data, list):
            #     self.outline = data
            # elif isinstance(data, dict):
            #     for key, value in data.items():
            #         if isinstance(value, list):
            #             self.outline = value
            #             break
            if "outline" in data and isinstance(data["outline"], list):
                self.outline = data["outline"]
            elif isinstance(data, list):
                # 如果直接返回数组
                self.outline = [{"title": item, "key_points": []} if isinstance(item, str) else item for item in data]
            else:
                # 尝试查找任何包含章节信息的键
                for key, value in data.items():
                    if isinstance(value, list) and len(value) > 0:
                        if isinstance(value[0], dict) and "title" in value[0]:
                            self.outline = value
                            break
                        elif isinstance(value[0], str):
                            self.outline = [{"title": title, "key_points": []} for title in value]
                            break
            if not self.outline:
                raise ValueError("未找到有效的大纲列表")

            print(f"✅ 大纲已生成: {self.outline}")

        except Exception as e:
            print(f"❌ 大纲生成失败: {e}")
            print(f"Raw Content: {content if 'content' in locals() else 'None'}")
            sys.exit(1)

    def step2_generate_content_loop(self):
        """Step 2: 循环生成内容，并维护 Context"""
        if not self.outline:
            return

        # 初始化上下文摘要
        previous_summary = "文章开始。"
        
        print("\n🚀 开始撰写正文...")
        for i, chapter in enumerate(self.outline):
            print(f"[{i+1}/{len(self.outline)}] 正在撰写: {chapter}...")
            
            # TODO: 构造 Prompt，核心在于 Context 的注入
            key_points_text="本章需要涵盖以下要点：\n" + "\n".join([f"- {point}" for point in chapter['key_points']])
            prompt = f"""
            你是一位专业作家。请撰写章节："{chapter}"。
            
            【前情提要】：
            {previous_summary}
            【本章写作要求】：
{key_points_text}

【具体指令】：
1. 内容充实，字数约300字。
2. 必须自然承接【前情提要】的逻辑，不要重复前文已详细阐述的内容
3. 保持专业且流畅的文风，为后续章节做好铺垫
4. 确保逻辑连贯，观点明确，论据充分

请开始撰写本章内容：

            """
            
            try:
                response = client.chat.completions.create(
                    model=MODEL_NAME,  # 使用配置的模型名
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7
                )
                content = response.choices[0].message.content
                self.articles.append(f"## {chapter}\n\n{content}")
                
                # TODO: 更新 Context (核心考察点)
                # 简单策略：截取最后 200 字
                previous_summary = self._update_context_summary(
                    previous_summary, chapter['title'], content, i
                )
                # previous_summary = content[-200:]
                
            except Exception as e:
                print(f"⚠️ 章节 {chapter} 生成失败: {e}")

    def _update_context_summary(self, current_summary, chapter_title, new_content, chapter_index):
        if chapter_index == 0:
            # 第一章：基于内容生成摘要
            summary_prompt = f"""
            请对以下文章章节内容生成一个简洁的摘要（100字左右），用于后续章节的上下文衔接：

            章节标题：{chapter_title}
            章节内容：{new_content}

            摘要要求：
            1. 提取核心观点和关键信息
            2. 保持逻辑连贯性
            3. 为下一章做好铺垫

            摘要：
            """

            try:
                response = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=[{"role": "user", "content": summary_prompt}],
                    temperature=0.3,
                    max_tokens=200
                )
                new_summary = response.choices[0].message.content
            except:
                # 如果摘要生成失败，使用智能截断
                new_summary = self.truncate_context(new_content, 150)
        else:
            # 后续章节：结合现有摘要和新内容生成更新摘要
            update_prompt = f"""
            现有文章摘要：{current_summary}

            新增章节内容：{new_content}

            请基于以上信息，生成一个更新的综合摘要（150字左右），要求：
            1. 保留前文的核心信息
            2. 融入新章节的关键内容
            3. 保持整体逻辑连贯
            4. 为下一章做好自然过渡

            更新后的摘要：
            """

            try:
                response = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=[{"role": "user", "content": update_prompt}],
                    temperature=0.3,
                    max_tokens=250
                )
                new_summary = response.choices[0].message.content
            except:
                # 降级方案：组合+截断
                combined = f"{current_summary}\n\n【{chapter_title}】主要内容：{self.truncate_context(new_content, 100)}"
                new_summary = self.truncate_context(combined, 200)

        return new_summary

    def save_result(self):
        if not self.articles:
            print("⚠️ 没有生成任何内容")
            return
            
        filename = "final_article.md"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"# {self.topic}\n\n")
            f.write("\n\n".join(self.articles))
        print(f"\n🎉 文章已保存至 {filename}")

if __name__ == "__main__":
    print(f"🔌 Endpoint: {BASE_URL}")
    print(f"🧠 Model: {MODEL_NAME}\n")
    
    agent = LongArticleAgent("2025年 DeepSeek 对 AI 行业的影响")
    agent.step1_generate_outline()
    agent.step2_generate_content_loop()
    agent.save_result()
