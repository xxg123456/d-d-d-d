import os
import time
import requests
import base64
from io import BytesIO
from PIL import Image

def index(event, context):
    event = ExecuteEvent(event, context)
    return event.execute()

class ExecuteEvent:
    def __init__(self, event, context):
        self.event = event
        self.context = context
        self.code = event["code"]

    def execute(self):
        '''执行事件'''
        if self.code == 300:
            return self.handleCapcha()
        else:
            return "什么都没有干"
    
    def handleCapcha(self):
        import re
        
        # 1. 提取今日校园发来的验证码数据
        capCode = self.context['capcode']
        target_name = capCode['result']['name'] 
        image_infos = capCode['result']['imageInfos'] 

        print(f"[{target_name}] 开始处理九宫格验证码，准备高清拼接图片...")

        # 2. 下载并拼接 9 张图片
        try:
            imgs = []
            for info in image_infos:
                img_url = info['path']
                img_res = requests.get(img_url, verify=False)
                imgs.append(Image.open(BytesIO(img_res.content)))
            
            w, h = imgs[0].size
            grid = Image.new('RGB', (w * 3, h * 3))
            
            for i, img in enumerate(imgs):
                grid.paste(img, (w * (i % 3), h * (i // 3)))
            
            # ⚠️ 秘密武器：删除了之前的 resize 压缩代码！
            # 保持原画质高清拼接，让通义千问大模型能看清"香蕉"的每一个细节！
            
            buffered = BytesIO()
            grid.save(buffered, format="JPEG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
            
        except Exception as e:
            raise Exception(f"图片下载或拼接失败: {str(e)}")

        # =========================================================
        # 3. 终极救场大模型：对接阿里通义千问视觉版 (Qwen-VL-Max)
        # =========================================================
        
        # 去阿里云百炼大模型平台申请的 API Key
        qwen_api_key = "sk-7c6d8a2ef1f34dd792dbe36b8e1280fa"  
        
        # 阿里云百炼的 OpenAI 兼容接口 (国内直连，拒绝报错)
        api_url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions" 
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {qwen_api_key}"
        }
        
        # 给通义千问下达严格的身份指令
        prompt = f"这是一张3x3的九宫格图片，按照从左到右、从上到下的顺序，编号依次为0到8。请帮我找出所有包含“{target_name}”的图片编号。请严格只返回一个包含编号数字的数组，例如：[0, 2, 5]。不要输出任何解释性的文字！"
        
        payload = {
            "model": "qwen-vl-max",  # 目前国内视觉识别能力最顶级的模型
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{img_base64}"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 50,
            "temperature": 0.1 
        }
        
        try:
            print(f"正在向 阿里通义千问 提交 [{target_name}] 识别任务...")
            response = requests.post(api_url, headers=headers, json=payload).json()
            
            # 捕获接口可能返回的错误信息
            if 'error' in response:
                raise Exception(f"通义千问 接口报错: {response['error'].get('message')}")
                
            # 获取大模型的文本回答
            ai_reply = response['choices'][0]['message']['content']
            print(f"通义千问 原始回答: {ai_reply}")
            
            # ---------------------------------------------------------
            # 4. 暴力提取与格式化
            # ---------------------------------------------------------
            extracted_numbers = re.findall(r'\d+', ai_reply)
            
            selected_codes = []
            for num_str in extracted_numbers:
                idx = int(num_str)
                if 0 <= idx < 9 and idx < len(image_infos):
                    selected_codes.append(image_infos[idx]['code'])
            
            # 数组去重
            selected_codes = list(set(selected_codes))
            
            if not selected_codes:
                raise Exception("通义千问 未能识别出任何有效数字，可能是没有找到符合要求的图片。")
                
            print(f"大模型提取成功！即将提交给教务系统的纯数组: {selected_codes}")
            
            return selected_codes 
                
        except Exception as e:
            raise Exception(f"通义千问 打码流程崩溃: {str(e)}") 
        #     # ---------------------------------------------------------
        #     # 4. 组装今日校园需要的返回值 (极简模式)
        #     # ---------------------------------------------------------
        #     objects = solution.get('objects', [])
            
        #     selected_codes = []
        #     for index in objects:
        #         idx = int(index)
        #         if idx < len(image_infos):
        #             selected_codes.append(image_infos[idx]['code'])
            
        #     # ⚠️ 这里是最终的秘密武器：什么包装都不要加！直接返回包含 32 位码的纯数组！
        #     print(f"即将提交给教务系统的纯数组: {selected_codes}")
            
        #     return selected_codes 
                
        # except Exception as e:
        #     raise Exception(f"YesCaptcha 打码流程崩溃: {str(e)}")        

    
#     def handleCapcha(self):
#         '''验证码识别'''
#         import os
#         mode = 1 if os.path.isdir("_userdefined_capt") else 0
#         capCode = self.context["capcode"]

#         # ===============在线识别===============
#         if mode == 0:
#             from liteTools import reqSession, LL, DT, HSF, ST
#             # 检测解谜是否完成
#             if os.environ.get("CPDAILY_APPLE"):
#                 apple = os.environ["CPDAILY_APPLE"]
#             else:
#                 apple = DT.loadYml("config.yml").get("apple", "")
#             if not apple:
#                 raise Exception("""图片验证码识别错误: 
# 请在配置文档中填写apple项""")
#             else:
#                 # [对想逃课的人说的话: sha256是不可逆的(何况还加了盐)]
#                 hashApple = HSF.strHash(apple+'salt_apple_is_nice', 256)
#                 LL.log(
#                     1, f"苹果哈希「{hashApple}」")
#                 rightAppleHash = ("350fb0c1f9255ddd0a3a6cbfdb88a1f112d1d55618d3ed8864954186a7b0eb83",  # 新苹果
#                                   "cfeeeeb1d8f935a8ea7e4c0ab56b101dbdf9e8ce8cd3853a293a37e68b573ae6")  # 旧苹果
#                 if hashApple not in rightAppleHash:
#                     LL.log(2, ST.notionStr("""疑似错误的苹果:
# 请确定, 当你找到apple时, 看到了「恭喜你找到了apple」这句话"""))
#             # 开始验证码识别
#             LL.log(1, "即将进行验证码识别")
#             res = reqSession().post(apple, json=capCode)
#             res = res.json()
#             LL.log(1, "验证码识别返回值", res)
#             # 处理返回结果
#             if res["code"] not in (200, 400):
#                 '''识别出错'''
#                 raise Exception(f"使用验证码识别API识别出错『{res}』")
#             return res["data"]["succCode"]
#         # ===============本地识别===============
#         elif mode == 1:
#             from _userdefined_capt import captchaHandler
#             return captchaHandler(capCode)["right"]
#         # ===============报错===============
#         else:
#             '''报错'''
#             raise Exception(
#                 "图片验证码识别错误: \n验证码问题未解决, 请手签(就是用今日校园app自己手动签到的意思)\n错误信息")
# import time
# import requests
# import base64
# from io import BytesIO
# from PIL import Image

# def handleCapcha(self):
#     # 1. 提取今日校园发来的验证码数据
#     capCode = context['capcode']
#     target_name = capCode['result']['name'] # 题目，例如: "摩托车"
#     image_infos = capCode['result']['imageInfos'] # 包含 9 个图片链接的列表
    
#     print(f"[{target_name}] 开始处理九宫格验证码，准备拼接图片...")

#     # 2. 下载并拼接 9 张图片 (因为打码平台需要一张完整的 3x3 大图)
#     try:
#         imgs = []
#         for info in image_infos:
#             img_url = info['path']
#             # 下载图片
#             img_res = requests.get(img_url, verify=False)
#             imgs.append(Image.open(BytesIO(img_res.content)))
        
#         # 获取单张图片宽高，创建 3x3 的大图画布
#         w, h = imgs[0].size
#         grid = Image.new('RGB', (w * 3, h * 3))
        
#         # 将 9 张图按顺序贴到大图上
#         for i, img in enumerate(imgs):
#             grid.paste(img, (w * (i % 3), h * (i // 3)))
        
#         # 将拼好的大图转为 Base64 格式
#         buffered = BytesIO()
#         grid.save(buffered, format="JPEG")
#         img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
#         print("图片拼接并转换 Base64 完成！")
        
#     except Exception as e:
#         raise Exception(f"图片下载或拼接失败: {str(e)}")

#     # =========================================================
#     # 3. 对接 YesCaptcha 打码平台
#     # =========================================================
#     client_key = "34ef524608d4f962a7f3a8c44f90da676df41134120429"
    
#     # 构建任务数据
#     payload = {
#         "clientKey": client_key,
#         "task": {
#             "type": "ReCaptchaV2Classification", # 官方推荐的 3x3 九宫格分类任务
#             "image": img_base64,        
#             "question": target_name    
#         }
#     }
    
#     try:
#         # 第一步：提交任务
#         print(f"正在向 YesCaptcha 提交 [{target_name}] 识别任务...")
#         create_res = requests.post("https://api.yescaptcha.com/createTask", json=payload).json()
        
#         if create_res.get('errorId') != 0:
#             raise Exception(f"提交任务失败: {create_res.get('errorDescription')}")
            
#         task_id = create_res.get('taskId')
#         print(f"提交成功，获得任务单号: {task_id}，开始轮询结果...")
        
#         # 第二步：轮询等待结果（最多等 15 次，每次 2 秒）
#         result_payload = {
#             "clientKey": client_key,
#             "taskId": task_id
#         }
        
#         solution = None
#         for i in range(15):
#             time.sleep(2) # 必须等待，AI 识别需要时间
#             res = requests.post("https://api.yescaptcha.com/getTaskResult", json=result_payload).json()
#             status = res.get('status')
            
#             if status == 'ready':
#                 solution = res.get('solution')
#                 print(f"识别完成！耗时 {(i+1)*2} 秒，结果: {solution}")
#                 break
#             elif status == 'processing':
#                 print(f"正在识别中，已等待 {(i+1)*2} 秒...")
#                 continue
#             else:
#                 raise Exception(f"打码异常中断: {res}")
                
#         if not solution:
#             raise Exception("打码超时，AI 未能在 30 秒内返回结果")

#         # ---------------------------------------------------------
#         # 4. 组装今日校园需要的返回值
#         # ---------------------------------------------------------
#         # YesCaptcha 返回的 solution 格式通常为 {"objects": [0, 2, 5]} 
#         # (注意：它是从 0 开始计数的，0代表左上角第一张图)
#         objects = solution.get('objects', [])
        
#         # 将索列表 [0, 2, 5] 传给外层逻辑
#         selected_indices = [int(x) for x in objects]
        
#         return {
#             "code": 200,
#             "msg": "success",
#             "data": selected_indices
#         }
            
#     except Exception as e:
#         raise Exception(f"YesCaptcha 打码流程崩溃: {str(e)}")
