import tkinter as tk
from datetime import datetime
import json
import logging
import os
import time
import keyboard
import pyautogui
import cv2
import numpy as np
from paddleocr import PaddleOCR
import threading
from PIL import Image

# 全局变量
keys_config = None
mode1_purchase_btn_location = None
mode2_purchase_btn_location = None
is_running = False
is_paused = False
is_debug = False
screen_width, screen_height = pyautogui.size()

# 价格全局变量
ideal_price = 2000000
mode2_ideal_price = 100

# 延迟全局变量
mode1_delay_time = 0.1
mode2_delay_time = 0.17

# 禁用 PaddleOCR 调试日志
os.environ["PPOCR_LOG_LEVEL"] = "ERROR"
logging.getLogger("ppocr").setLevel(logging.ERROR)

# 初始化 PaddleOCR
ocr = PaddleOCR(use_angle_cls=True, lang='ch')  # 支持中文
ocr_english = PaddleOCR(use_angle_cls=True, lang='en')  # 使用英文模型

# 配置部分
CONFIG_FILE = 'config.json'

# 创建或更新日志输出函数
def log_message(message):
    print(message)
    if hasattr(app, 'log_text') and app.log_text:
        app.log_text.insert(tk.END, message + '\n')
        app.log_text.see(tk.END)

def ensure_images_folder_exists():
    """确保 images 文件夹存在"""
    if not os.path.exists("./images"):
        os.makedirs("./images")

def load_config():
    """加载配置文件"""
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
            return json.loads(content)
    except FileNotFoundError:
        log_message(f"[错误] 配置文件 {CONFIG_FILE} 不存在")
        return {}
    except json.JSONDecodeError as e:
        log_message(f"[错误] 配置文件 {CONFIG_FILE} 格式错误: {e}")
        return {}
    except Exception as e:
        log_message(f"[错误] 读取配置时发生未知错误: {str(e)}")
        return {}

def get_region_from_config(config, key):
    """从配置文件中获取区域"""
    region = config.get(key)
    if not region or len(region) != 4:
        log_message(f"[错误] 配置文件中缺少有效的 {key} 字段，请检查配置文件")
        return None
    return tuple(region)

def take_screenshot_cv(region, threshold):
    """使用 OpenCV 截图并进行二值化处理"""
    try:
        with pyautogui.screenshot(region=region) as screenshot:
            gray_array = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2GRAY)
            _, binary_array = cv2.threshold(gray_array, threshold, 255, cv2.THRESH_BINARY_INV)
            return Image.fromarray(binary_array)
    except Exception as e:
        log_message(f"[错误] 截图失败: {str(e)}")
        return None

def get_item_price(config, moden_p):
    """获取当前门卡价格，仅识别阿拉伯数字"""
    region = get_region_from_config(config, moden_p)
    if not region:
        return None

    image = take_screenshot_cv(region=region, threshold=55)
    if not image:
        return None

    image.save("./images/item_price.png")
    # 使用 PaddleOCR 识别价格
    result = ocr_english.ocr("./images/item_price.png", cls=False)
    if not result or not result[0]:
        log_message("无法识别价格")
        return None

    # 提取识别的文本
    text = result[0][0][1][0]  # 获取第一个识别结果的文字部分

    if is_debug:
        log_message(f"提取的门卡原始价格文本------------: {text}")

    # 只保留数字字符
    text = ''.join(filter(str.isdigit, text))

    if not text:
        log_message("未识别到有效数字")
        return None

    try:
        price = int(text)
        log_message(f"提取的门卡价格文本: {price}")
        return price
    except ValueError:
        log_message("无法解析价格")
        return None

def get_item_name(config):
    """获取当前物品名称"""
    region = get_region_from_config(config, "item_name_range")
    if not region:
        return None

    screenshot = take_screenshot_cv(region=region, threshold=100)
    if not screenshot:
        return None

    screenshot.save("./images/item_name.png")
    # 使用 PaddleOCR 识别物品名称
    result = ocr.ocr("./images/item_name.png", cls=True)
    if not result or not result[0]:
        log_message("无法识别物品名称")
        return None

    # 提取识别的文本
    text = result[0][0][1][0]  # 获取第一个识别结果的文字部分
    log_message(f"提取的物品名称文本: {text}")
    return text.replace(" ", "").strip()

def log_purchase(card_name, ideal_price, price, premium):
    """记录购买信息到 logs.txt"""
    log_entry = f"购买时间：{datetime.now():%Y-%m-%d %H:%M:%S} | 门卡名称: {card_name} | 理想价格: {ideal_price} | 购买价格: {price} | 溢价: {premium:.2f}% \n"
    with open("logs.txt", "a", encoding="utf-8") as log_file:
        log_file.write(log_entry)
    log_message(log_entry)

def Mode1(config):
    """Mode1 购买流程"""
    global mode1_purchase_btn_location

    position =  [0.1214, 0.4731]
    pyautogui.press('L')
    pyautogui.moveTo(position[0] * screen_width, position[1] * screen_height)  # mode1位置
    pyautogui.click()
    pyautogui.sleep(mode1_delay_time)
    current_price = get_item_price(config,"mode1_item_price_range")

    # 获取价格
    if current_price is None:
        log_message("无法获取有效价格，跳过本次检查")
        pyautogui.press('esc')
        return False

    premium = ((current_price / ideal_price) - 1) * 100  # 溢价率

    if premium < 0 or current_price < ideal_price:
        # 点击购买按钮
        pyautogui.moveTo(mode1_purchase_btn_location[0] * screen_width, mode1_purchase_btn_location[1] * screen_height)
        pyautogui.click()
        log_purchase("模式一成功购买！", ideal_price, current_price, premium)
        pyautogui.press('esc')
        time.sleep(mode1_delay_time)  # 添加模式1的延迟
        return True
    else:
        log_message("价格过高，重新刷新价格")
        pyautogui.press('esc')
        time.sleep(mode1_delay_time)
        return False

def Mode2(config):
    """Mode2 购买流程"""
    global mode2_purchase_btn_location

    position = [0.2786, 0.2361]
    pyautogui.moveTo(position[0] * screen_width, position[1] * screen_height)  # mode1位置
    pyautogui.click()

    mode2_200 =  [0.9078, 0.7194]
    mode2_plus = [0.9313, 0.7194]
    time.sleep(mode2_delay_time)
    current_price = get_item_price(config, "mode2_item_price_range")

    # 获取价格
    if current_price is None:
        log_message("无法获取有效价格，跳过本次检查")
        pyautogui.press('esc')
        return False

    premium = ((current_price / mode2_ideal_price) - 1) * 100  # 溢价率

    if premium < 0 or current_price < mode2_ideal_price:
        # 选择200
        pyautogui.moveTo(mode2_200[0] * screen_width, mode2_200[1] * screen_height)
        pyautogui.click()
        # 确保是200
        pyautogui.moveTo(mode2_plus[0] * screen_width, mode2_plus[1] * screen_height)  # 点击+号
        # 多次鼠标点击
        for i in range(2):
            pyautogui.click()
        # 点击购买按钮
        
        
        pyautogui.moveTo(mode2_purchase_btn_location[0] * screen_width, mode2_purchase_btn_location[1] * screen_height)
        pyautogui.click()
        log_purchase("模式二成功购买！", mode2_ideal_price, current_price, premium)
        time.sleep(mode2_delay_time)  # 添加模式2的延迟
        pyautogui.press('esc')
        return True
    else:
        log_message("价格过高，重新刷新价格")
        pyautogui.press('esc')
        time.sleep(mode2_delay_time)
        return False

def main():
    global is_running
    global app
    global mode1_purchase_btn_location
    global mode2_purchase_btn_location

    # 加载按键配置
    config = load_config()

    # 确保 images 文件夹存在
    ensure_images_folder_exists()

    # 从配置文件中获取 purchase_btn_location 的值
    mode1_purchase_btn_location = [0.8214, 0.7954]
    mode2_purchase_btn_location = [0.8495, 0.7843]

    # 初始化应用界面
    root = tk.Tk()# 创建窗口
    root.title("mgbuy")
    app = Application(config, master=root)
    app.start_background_thread()
    app.mainloop()

class Application(tk.Frame):
    def __init__(self, config, master=None):
        super().__init__(master)
        self.master = master
        self.pack()
        self.config = config
        self.create_widgets()
        self.setup_hotkeys()
        self.update_config_display()
        self.background_thread = None
        self.background_running = False

    def create_widgets(self):
        # 创建模式选择部分
        self.mode_frame = tk.LabelFrame(self, text="选择模式")
        self.mode_frame.pack(fill="x", padx=10, pady=10)

        self.mode_var = tk.IntVar()
        self.mode1_radio = tk.Radiobutton(self.mode_frame, text="模式1", variable=self.mode_var, value=1,
                                          command=self.update_mode)
        self.mode1_radio.pack(side="left", padx=10, pady=5)

        self.mode2_radio = tk.Radiobutton(self.mode_frame, text="模式2", variable=self.mode_var, value=2,
                                          command=self.update_mode)
        self.mode2_radio.pack(side="left", padx=10, pady=5)

        # 创建价格设置部分
        self.price_frame = tk.LabelFrame(self, text="价格设置")
        self.price_frame.pack(fill="x", padx=10, pady=10)

        # 模式1价格
        self.mode1_price_label = tk.Label(self.price_frame, text="模式1理想价格:")
        self.mode1_price_label.grid(row=0, column=0, padx=10, pady=5, sticky="w")

        self.mode1_price_var = tk.StringVar()
        self.mode1_price_entry = tk.Entry(self.price_frame, textvariable=self.mode1_price_var, width=15)
        self.mode1_price_entry.grid(row=0, column=1, padx=10, pady=5)

        # 模式2价格
        self.mode2_price_label = tk.Label(self.price_frame, text="模式2理想价格:")
        self.mode2_price_label.grid(row=1, column=0, padx=10, pady=5, sticky="w")

        self.mode2_price_var = tk.StringVar()
        self.mode2_price_entry = tk.Entry(self.price_frame, textvariable=self.mode2_price_var, width=15)
        self.mode2_price_entry.grid(row=1, column=1, padx=10, pady=5)

        # 保存价格按钮
        self.save_price_button = tk.Button(self.price_frame, text="保存价格", command=self.save_prices)
        self.save_price_button.grid(row=0, column=2, rowspan=2, padx=10, pady=5)

        # 创建延迟设置部分
        self.delay_frame = tk.LabelFrame(self, text="延迟设置")
        self.delay_frame.pack(fill="x", padx=10, pady=10)

        # 模式1延迟
        self.mode1_delay_label = tk.Label(self.delay_frame, text="模式1延迟时间 (秒):")
        self.mode1_delay_label.grid(row=0, column=0, padx=10, pady=5, sticky="w")

        self.mode1_delay_var = tk.StringVar(value=str(mode1_delay_time))
        self.mode1_delay_entry = tk.Entry(self.delay_frame, textvariable=self.mode1_delay_var, width=15)
        self.mode1_delay_entry.grid(row=0, column=1, padx=10, pady=5)

        # 模式2延迟
        self.mode2_delay_label = tk.Label(self.delay_frame, text="模式2延迟时间 (秒):")
        self.mode2_delay_label.grid(row=1, column=0, padx=10, pady=5, sticky="w")

        self.mode2_delay_var = tk.StringVar(value=str(mode2_delay_time))
        self.mode2_delay_entry = tk.Entry(self.delay_frame, textvariable=self.mode2_delay_var, width=15)
        self.mode2_delay_entry.grid(row=1, column=1, padx=10, pady=5)

        # 保存延迟按钮
        self.save_delay_button = tk.Button(self.delay_frame, text="保存延迟", command=self.save_delays)
        self.save_delay_button.grid(row=0, column=2, rowspan=2, padx=10, pady=5)

        # 创建控制按钮部分
        self.control_frame = tk.Frame(self)
        self.control_frame.pack(fill="x", padx=10, pady=10)

        self.start_button = tk.Button(self.control_frame, text="开始执行(F8)", command=lambda: set_running_state(True))
        self.start_button.pack(side="left", padx=10, pady=5)

        self.stop_button = tk.Button(self.control_frame, text="停止执行(F9)", command=lambda: set_running_state(False))
        self.stop_button.pack(side="left", padx=10, pady=5)

        # 创建日志显示部分
        self.log_frame = tk.LabelFrame(self, text="日志输出")
        self.log_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.log_text = tk.Text(self.log_frame, height=10, width=80)
        self.log_text.pack(side="left", fill="both", expand=True, padx=5, pady=5)

        self.log_scrollbar = tk.Scrollbar(self.log_frame, command=self.log_text.yview)
        self.log_scrollbar.pack(side="right", fill="y")
        self.log_text.config(yscrollcommand=self.log_scrollbar.set)

    def setup_hotkeys(self):
        keyboard.add_hotkey('f8', lambda: set_running_state(True))
        keyboard.add_hotkey('f9', lambda: set_running_state(False))

    def update_mode(self):
        mode = self.mode_var.get()
        self.config['mode'] = mode
        log_message(f"已选择模式{mode}")

    def save_prices(self):
        global ideal_price, mode2_ideal_price
        try:
            ideal_price = int(self.mode1_price_var.get())
            mode2_ideal_price = int(self.mode2_price_var.get())
            log_message(f"已保存价格：模式1={ideal_price}，模式2={mode2_ideal_price}")
        except ValueError:
            log_message("请输入有效的数字价格")

    def save_delays(self):
        global mode1_delay_time, mode2_delay_time
        try:
            mode1_delay_time = float(self.mode1_delay_var.get())
            mode2_delay_time = float(self.mode2_delay_var.get())
            log_message(f"已保存延迟：模式1={mode1_delay_time}秒，模式2={mode2_delay_time}秒")
        except ValueError:
            log_message("请输入有效的数字延迟")

    def update_config_display(self):
        mode = self.config.get("mode", 1)
        self.mode_var.set(mode)

        self.mode1_price_var.set(str(ideal_price))
        self.mode2_price_var.set(str(mode2_ideal_price))
        self.mode1_delay_var.set(str(mode1_delay_time))
        self.mode2_delay_var.set(str(mode2_delay_time))

    def start_background_thread(self):
        self.background_thread = threading.Thread(target=self.run_background)
        self.background_thread.daemon = True  # 设置为守护线程
        self.background_thread.start()

    def run_background(self):
        while True:
            if is_running:
                mode = self.config.get("mode", 1)
                if mode == 1:
                    Mode1(self.config)
                elif mode == 2:
                    Mode2(self.config)
                else:
                    log_message("未知模式，请检查配置文件")
            time.sleep(0.1)

global app
app = None

def set_running_state(state):
    global is_running, app
    is_running = state
    if app:
        if state:
            app.start_button.config(state="disabled")
            app.stop_button.config(state="normal")
            log_message("开始执行任务")
        else:
            app.start_button.config(state="normal")
            app.stop_button.config(state="disabled")
            log_message("任务已停止")

if __name__ == '__main__':
    main()