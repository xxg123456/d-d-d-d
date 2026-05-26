import os
import subprocess
import threading
import requests
import json
import re
from flask import Flask, request, jsonify
import yaml
# 🌟 新增导入 liteTools 中的 CpdailyTools 模块
from liteTools import CpdailyTools
import os
import glob

def get_latest_log_content(log_dir="_log/"):
    """获取指定目录下最新生成的日志文件内容"""
    try:
        if not os.path.exists(log_dir):
            return "日志目录不存在"
            
        # 获取目录下所有文件列表
        files = glob.glob(os.path.join(log_dir, "*"))
        if not files:
            return "暂无日志文件"
            
        # 按文件最后修改时间排序，取最新的一个
        latest_file = max(files, key=os.path.getmtime)
        
        # 读取内容（建议只读取最后 2000 字符，防止日志过大撑爆 JSON）
        with open(latest_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            return content[-2000:] if len(content) > 2000 else content
            
    except Exception as e:
        return f"读取日志失败: {str(e)}"   
        # 日志函数上面

app = Flask(__name__)
lock = threading.Lock()

@app.route('/api/sign', methods=['POST'])
def sign_api():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    school = data.get('school')
    # 新增接收一个具体的地址参数，如果没有传，就降级使用 school 名称
    address = data.get('address', school)
    photo_url = data.get('photo', '')

    # 提前获取 PHP 传过来的兜底坐标（不要做强制校验拦截，只是先拿出来备用）
    req_lon = data.get('lon')
    req_lat = data.get('lat')
    
    # # 🌟 直接接收前端传来的经纬度 (不再自己去查地图)
    # lon = data.get('lon')
    # lat = data.get('lat')
    # # 校验：确保前端必须把坐标传过来
    # if not all([username, password, school, lon, lat]):
    #     return jsonify({'code': 400, 'msg': '参数不全，请确保经纬度已填写'})
    
    # 校验：基础参数是否齐全
    if not all([username, password, school, address]):
        return jsonify({'code': 400, 'msg': '参数不全，请确保账号、密码、学校名称,地址已填写'})

    lon, lat = None, None
    
    # 🌟 核心修改：通过后端自动获取经纬度，完全抛弃/覆盖前端传来的 lon 和 lat
    # try:
    #     # 传入学校名称获取坐标 (返回的是元组: (lon, lat))
    #     lon, lat = CpdailyTools.baiduGeocoding(address)
    # except Exception as e:
    #     # 如果学校名字填得太离谱，或者 API 抽风，拦截错误并返回给前端
    #     return jsonify({'code': 500, 'msg': f'获取学校经纬度失败，请检查学校名称是否正确。错误信息：{str(e)}'})
    # 🌟 核心修改：双保险获取坐标机制

    
    
    try:
        print(f"【大模型启动】正在解析地址：{address}")
        
        qwen_api_key = "sk-7c6d8a2ef1f34dd792dbe36b8e1280fa"  
        api_url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions" 
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {qwen_api_key}"
        }
        
        # 1. 问大模型：下达严格指令
        payload = {
            "model": "qwen-max", 
            "messages": [
                {
                    "role": "system",
                    "content": "你是一个坐标转换API。请输出给定地址的百度地图经纬度。必须且只能回复包含lon和lat的JSON，不要解释，不要使用Markdown标记。"
                },
                {
                    "role": "user",
                    "content": f"目标地址：{address}"
                }
            ],
            "temperature": 0.01 # 极低温度，保证格式稳定
        }
        
        # 发送网络请求
        resp = requests.post(api_url, headers=headers, json=payload, timeout=15)
        resp.raise_for_status()
        
        # 2. 获取大模型的原始回答
        result_text = resp.json()['choices'][0]['message']['content']
        print(f"[AI 原始回复]：\n{result_text}")
        
        # 3. 定位并提取经纬度 (核心救场逻辑)
        # 使用正则表达式寻找字符串中第一对 { } 及其里面的内容
        json_match = re.search(r'\{[^{}]*\}', result_text, re.DOTALL)
        
        if json_match:
            # 提取出纯净的 JSON 字符串
            clean_json_str = json_match.group()
            
            # 将字符串转换为 Python 字典
            coord_data = json.loads(clean_json_str)
            
            # 4. 赋值给最终变量
            lon = str(coord_data.get('lon', ''))
            lat = str(coord_data.get('lat', ''))
            
            # 校验大模型是不是随便回了个空字段
            if not lon or not lat or lon == 'None' or lat == 'None':
                raise ValueError("大模型返回的 JSON 中缺少 lon 或 lat 字段")
                
            print(f"✅ 成功定位并赋值坐标: lon={lon}, lat={lat}")
            
        else:
            # 如果正则表达式没有找到 { }，说明大模型完全没按格式回答
            raise ValueError("大模型的回复中未找到合法的 JSON 结构")

    except Exception as e:
        print(f"❌ 大模型获取/解析彻底失败，原因：{str(e)}")
        print("【启动兜底】启用 PHP 传来的 OSM 坐标...")
        
        # 赋值失败时，自动退回到第二道防线（PHP传来的坐标）
        lon = req_lon
        lat = req_lat

    # 最终的安全校验：如果两边都拿不到坐标，才真正报错返回给前端
    if not lon or not lat:
        return jsonify({
            'code': 500, 
            'msg': '获取地址经纬度彻底失败（后端 API 与前置免 Key 算法双双失效），请联系管理员检查网络环境。'
        })

    with lock:
        try:
            # ==========================================
            # 第一步：先读取现有的 config.yml 获取旧配置
            # ==========================================
            if os.path.exists("config.yml"):
                with open("config.yml", "r", encoding="utf-8") as f:
                    existing_config = yaml.safe_load(f) or {}
            else:
                existing_config = {} # 如果文件不存在，就给个空字典
            
            # ==========================================
            # 第二步：将前端传来的新用户数据，覆盖到现有的配置中
            # ==========================================
            # 这里我们只修改 'users' 这个列表，其他全局配置（如推送、打码等）原封不动
            existing_config['users'] = [
                    # 任务一：日常签到 (type: 1)
                {
                    'type': 1,         
                    'schoolName': school,
                    'username': username,
                    'password': password,
                    'signLevel': 1,
                    'title': 0,
                    'checkTitle': 0,
                    'abnormalReason': "", 
                    'lon': float(lon),  
                    'lat': float(lat),  
                    'address': address,
                    'photo': photo_url,
                    'deviceId': "B165F069-7E39-7B5B-2DA5-07B0EC4BFBF8" # 🌟🌟 核心防封锁：强制锁死设备码 🌟🌟# 🌟 新增
                },
                # 任务二：查寝签到 (type: 2)
                {
                    'type': 2,         
                    'schoolName': school,
                    'username': username,
                    'password': password,
                    'signLevel': 1,
                    'title': 0,
                    'checkTitle': 0,
                    'abnormalReason': "", 
                    'lon': float(lon),  
                    'lat': float(lat),  
                    'address': address,
                    'photo': photo_url,
                    'deviceId': "B165F069-7E39-7B5B-2DA5-07B0EC4BFBF8" # 🌟🌟 核心防封锁：强制锁死设备码 🌟🌟
                }
                    
            ]

            # ==========================================
            # 第三步：将混合后的完整配置，重新写回文件
            # ==========================================
            with open("config.yml", "w", encoding="utf-8") as f:
                yaml.dump(existing_config, f, allow_unicode=True, sort_keys=False)
            # # 1. 构造若离需要的 config.yml 格式
            # user_config = {
            #     # --- 🌟 以下是补充的全局通用配置，写死在代码里解决 KeyError 报错 ---
            #     'apple': "https://apple.ruoli.cc/captcha/validate",
            #     'locationOffsetRange': 50, # 签到坐标随机偏移范围(单位：米)
            #     'maxTry': 3,               # 最大尝试次数
            #     'logDir': "_log/",         # 日志保存地址
            #     'delay': [5, 10],          # 多用户延迟
            #     'captcha': {},             # 留空，不配置验证码推送
            #     'sendMessage': {},         # 留空，不配置消息推送
                
            #     # --- 以下是前端传入的动态数据 ---
            #     'users': [
            #         {
            #             'type': 2,         # 2 为查寝，1 为签到 (按需调整)
            #             'schoolName': school,
            #             'username': username,
            #             'password': password,
            #             'signLevel': 1,
            #             'title': 0,
            #             'checkTitle': 0,
            #             'abnormalReason': "", # 补充缺失字段
            #             'lon': float(lon),  # 直接写入用户精准经度
            #             'lat': float(lat),  # 直接写入用户精准纬度
            #             'address': school,
            #             'photo': photo_url
            #         }
            #     ]
            # }
            
            
            # # 2. 写入配置文件
            # with open("config.yml", "w", encoding="utf-8") as f:
            #     yaml.dump(user_config, f, allow_unicode=True, sort_keys=False)
            
            # 3. 执行打卡脚本
            result = subprocess.run(["python", "index.py"], capture_output=True, text=True, cwd=".")
            output = result.stdout + result.stderr

            # 🌟 新增调用：去 _log/ 文件夹下把详细的日志捞出来
            # ==========================================
            execution_log = get_latest_log_content("_log/")
            
            # 把控制台最直接的输出 和 文件里的详细日志 拼接在一起，方便你排查一切问题！
            final_log = f"--- 控制台基础输出 ---\n{output}\n\n--- 底层执行详细日志 ---\n{execution_log}"  

            # 调用日志函数上面

            # 4. 分析执行日志 (🌟 核心修复：把里面的 output 全部换成 final_log！)
            if "签到成功" in output or "成功" in output or "success" in output.lower():
                return jsonify({'code': 200, 'msg': '签到成功', 'log': final_log})
            elif "密码错误" in output or "认证失败" in output:
                return jsonify({'code': 400, 'msg': '账号或密码错误', 'log': final_log}) # 🌟 补上 log
            elif "不需要" in output or "已签到" in output:
                return jsonify({'code': 200, 'msg': '当前不在签到时间或已完成签到', 'log': final_log}) # 🌟 补上 log
            else:
                return jsonify({'code': 400, 'msg': '签到失败，请检查坐标或稍后再试', 'log': final_log})
                
        except Exception as e:
            # 🌟 补上崩溃时的日志抓取
            crash_log = get_latest_log_content("_log/")
            return jsonify({
                'code': 500, 
                'msg': f"API执行异常: {str(e)}", 
                'log': f"系统崩溃日志:\n{crash_log}"
            })

        #     # 4. 分析执行日志
        #     if "签到成功" in output or "成功" in output or "success" in output.lower():
        #         return jsonify({'code': 200, 'msg': '签到成功', 'log': output})
        #     elif "密码错误" in output or "认证失败" in output:
        #         return jsonify({'code': 400, 'msg': '账号或密码错误'})
        #     elif "不需要" in output or "已签到" in output:
        #         return jsonify({'code': 200, 'msg': '当前不在签到时间或已完成签到'})
        #     else:
        #         return jsonify({'code': 400, 'msg': '签到失败，请检查坐标或稍后再试', 'log': output})
                
        # except Exception as e:
        #     return jsonify({'code': 500, 'msg': f"API执行异常: {str(e)}"})

# 增加一个简单的 ping 接口，用于 UptimeRobot 保活唤醒
@app.route('/ping', methods=['GET'])
def ping():
    return jsonify({'code': 200, 'msg': 'pong'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
