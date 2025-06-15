import os
import requests
import json
import time
from datetime import datetime
import base64
import re
import uuid
import random

# =========================================================================================
# SECTION: HẰNG SỐ VÀ CẤU HÌNH (CONSTANTS & CONFIGURATION)
# =========================================================================================

# --- Mã màu cho Console ---
class Colors:
    BLACK = '\033[1;30m'
    RED = '\033[1;31m'
    GREEN = '\033[1;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[1;34m'
    PURPLE = '\033[1;35m'
    CYAN = '\033[1;36m'
    WHITE = '\033[1;37m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

# --- Cấu hình API của TraoDoiSub ---
TDS_BASE_URL = "https://traodoisub.com/api"
TDS_FIELDS_URL = f"{TDS_BASE_URL}/?fields="
TDS_COIN_URL = f"{TDS_BASE_URL}/coin/?type="

# --- Danh sách các loại nhiệm vụ được hỗ trợ ---
SUPPORTED_TASK_TYPES = [
    "facebook_reaction",
    "facebook_share",
    "facebook_follow",
    "facebook_page"
]

# --- ID cho các loại reaction trên Facebook ---
REACTION_IDS = {
    "LIKE": "1635855486666999",
    "LOVE": "1678524932434102",
    "CARE": "613557422527858",
    "HAHA": "115940658764963",
    "WOW": "478547315650144",
    "SAD": "908563459236466",
    "ANGRY": "444813342392137"
}

# =========================================================================================
# SECTION: CÁC LỚP XỬ LÝ CHÍNH (CORE CLASSES)
# =========================================================================================

class FacebookAccount:
    """Đại diện cho một tài khoản Facebook, chịu trách nhiệm lấy thông tin cần thiết."""
    def __init__(self, cookie):
        self.cookie = cookie
        self.name = None
        self.uid = None
        self.fb_dtsg = None
        self.is_valid = self._fetch_account_details()

    def _fetch_account_details(self):
        """Lấy các thông tin cần thiết (UID, Name, fb_dtsg) từ cookie."""
        try:
            if 'c_user=' not in self.cookie:
                print(f"{Colors.RED}Cookie không hợp lệ: Thiếu 'c_user'.{Colors.RESET}")
                return False

            self.uid = self.cookie.split('c_user=')[1].split(';')[0]
            headers = {
                'authority': 'www.facebook.com',
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'accept-language': 'vi-VN,vi;q=0.9,fr-FR;q=0.8,fr;q=0.7,en-US;q=0.6,en;q=0.5',
                'cookie': self.cookie,
                'sec-ch-ua': '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'document',
                'sec-fetch-mode': 'navigate',
                'sec-fetch-site': 'none',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            }

            response = requests.get('https://www.facebook.com/', headers=headers)
            if response.status_code != 200:
                print(f"{Colors.RED}Không thể truy cập Facebook (Status: {response.status_code}).{Colors.RESET}")
                return False

            fb_dtsg_match = re.search(r'"DTSGInitialData",\[\],{"token":"(.*?)"', response.text) or \
                            re.search(r'name="fb_dtsg" value="(.*?)"', response.text) or \
                            re.search(r'"async_get_token":"(.*?)"', response.text)

            if not fb_dtsg_match:
                print(f"{Colors.RED}Không thể lấy fb_dtsg. Cookie có thể đã hết hạn.{Colors.RESET}")
                return False
            self.fb_dtsg = fb_dtsg_match.group(1)

            name_match = re.search(r'"NAME":"(.*?)"', response.text)
            if name_match:
                self.name = name_match.group(1)
            else:
                mbasic_response = requests.get(f'https://mbasic.facebook.com/profile.php?id={self.uid}', headers=headers)
                self.name = mbasic_response.text.split('<title>')[1].split('</title>')[0]

            return True

        except Exception as e:
            print(f"{Colors.RED}Lỗi khi lấy thông tin Facebook: {str(e)}{Colors.RESET}")
            return False

class FacebookInteractor:
    """Thực hiện tất cả các hành động tương tác với Facebook (share, reaction, follow, page like)."""
    def __init__(self, fb_account: FacebookAccount):
        self.account = fb_account
        self.headers = {
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9",
            "content-type": "application/x-www-form-urlencoded",
            "cookie": self.account.cookie,
            "origin": "https://www.facebook.com",
            "priority": "u=1, i",
            "sec-ch-ua": '"Brave";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "sec-gpc": "1",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
            "x-asbd-id": "359341",
        }

    def _get_post_id(self, task_id):
        return task_id.split('_')[1] if '_' in task_id else task_id

    def _perform_reaction(self, task_id, reaction_name):
        """Thực hiện một reaction cụ thể (LIKE, LOVE, CARE, etc.) theo API mới nhất."""
        reaction_id = REACTION_IDS.get(reaction_name.upper())
        if not reaction_id:
            print(f"{Colors.RED}Loại reaction không hợp lệ: {reaction_name}{Colors.RESET}")
            return False

        post_id = self._get_post_id(task_id)
        feedback_id = base64.b64encode(f"feedback:{post_id}".encode()).decode()

        headers = self.headers.copy()
        headers.update({
            'referer': 'https://www.facebook.com/',
            'x-fb-friendly-name': 'CometUFIFeedbackReactMutation',
        })

        attribution_id = f"CometHomeRoot.react,comet.home,tap_tabbar,{int(time.time()*1000)},594426,4748854339,,"
        
        variables = {
            "input": {
                "attribution_id_v2": attribution_id,
                "feedback_id": feedback_id,
                "feedback_reaction_id": reaction_id,
                "feedback_source": "NEWS_FEED",
                "feedback_referrer": "/",
                "is_tracking_encrypted": True,
                "tracking": None,
                "session_id": str(uuid.uuid4()),
                "actor_id": self.account.uid,
                "client_mutation_id": str(random.randint(1, 10))
            },
            "useDefaultActor": False,
            "__relay_internal__pv__CometUFIReactionsEnableShortNamerelayprovider": False
        }

        lsd_val = "Kz8mR1dbHSzVWd4U41Tg_e"
        
        data = {
            "av": self.account.uid,
            "__user": self.account.uid,
            "__a": "1",
            "__req": "2h",
            "__hs": "20253.HYP:comet_pkg.2.1...0",
            "dpr": "1",
            "__ccg": "EXCELLENT",
            "__rev": "1023849647",
            "__s": "k54qqm:771bv2:j6o3ye",
            "__hsi": "7515765884117733295",
            "__dyn": "7xeUjGU9k9wxxt0koC8G6Ejh941twWwIxu13wFG3OubyQdwSAx-bwNwnof8boG4E762S1DwUx60xU8E5O0BU2_CxS320qa2OU7m2210wEwgo9oO0wE7u12wOx62G5Usw9m1cwLwBgK7o8o4u0Mo4G1hx-3m1mzXw8W58jwGzEjzFU5e7oqBwJK14xm3y3aexfxmu3W3jU8o4qum7-2K0SEuwLyEbUGdG0HE88cA0z8c84p1e4UK2K2WEjxK2B08-269wkopg6C13xecwBwWzUfHDzUiBG2OUqwjVqwLwHwGwto461wwVwe23a",
            "__csr": "g4B1Rk21sbNIdcOfkaP8l9R9tFht9jONQBii9bKx2-Httb9dbsWllRl8RmRRJsxmyQOEAlfZFSmGCUCHmRXtmBgyiAJPnluAFd5BFn9HztRrz4_AQiSL8RWlztTDnFbyaGBDVmiJ4BAjaLmilnCVqhVmF4mEz-BGAF4GyFfGmEyt5zoB6ABZ3bjpoyUiXAGdKm8GmDAKLASHzAl2QbFdOaVFoyuEkHADCyAQFaG5FuqumLHiWGmbUjG4UCqm9nmiulAiBBU-VQfDGWX-qimGgy9DWy8mxFQbQryKbBDCy8yFpeh928OC5A5-9iG8VoyUCFWy9KFENDgsDQFLyUGdIxby9Vaz8ggK2GnwCz8uUJt5V9aDzUCeyp8G2Kfl8x_y4AmidwGyGBz9EGqcCF0wU8odFVGwwxy78pDx16QRx2dwkolg20F5AGbwPhaxW1Ag98jQqmV9Uryo8p61awxwWxd0mo8o6-ey86G6pBwyAgN4ypE823UsGKyVqDoW2Wawj8GQ642qayoK7UCi9yAU2dwXyo2rU9o2vwWwOxqdxq1oAwBhix254A7em268oJt78uGg28xKU2HxO4WxyjwywKxAFU-1uG325oaEbS22261exq2ThSexzgyaz-PwTwCz8bpEshUuwWy8Xwjopguwhd0oE8od8B7xK3l0KgkjhF9agR1y9U4mayoWey8666UaE8Ejz8yqEgyU29y-ta4qy9FoAHxmEbWuC5EKmBojwlu68y1cVmmaGEjU2Rwm87mi74y3Tw-xO18F3U3dyo9E0Qe17m1Ga04Oo0yS02dq1vzA0To3IoR17wZgy9xVw1FuA04xU4-m7U06EOx4iEmxC0buw1ei0nq02dG0a1w3f83hG1UxGt38aU35o2Yw4ugfEO0KU3yDgcE2Pw9u0ouzTwfepwBw38U9CEkgnwXw8S0mS260KE2WwgUcE0CiU3qxa2S8CU2NwR4Ux2Uy0zE8U20Ao3dwsU5K5S0lYEcpA0sC0a8w6Se3G6o4y0tS0qiu3yAi362B0Roiwci3u1gEjEk86GAf9ic2G0EQ6Ub8G2aiew824o5Lg2vgdEjzQ7d4AjoC1FwJHwFwbG0W6_49yE3-Ag7V9eC4E3iwZg5S04Up2G0vi3mu0g20BUydxrGU4m4205Vzo1bXQ06dE1IU30qxi42z8bo4F45m8wHgboho1JE2hwgA0VUbUog0gg804vVim0GouwaZ04kw4OxRk0gilw",
      
            "__comet_req": "15",
            "fb_dtsg": self.account.fb_dtsg,
            "jazoest": "25378",
            "lsd": lsd_val,
            "__spin_r": "1023849647",
            "__spin_b": "trunk",
            "__spin_t": str(int(time.time())),
            "fb_api_caller_class": "RelayModern",
            "fb_api_req_friendly_name": "CometUFIFeedbackReactMutation",
            "variables": json.dumps(variables),
            "server_timestamps": "true",
            "doc_id": "9518016021660044"
        }
        
        try:
            response = requests.post("https://www.facebook.com/api/graphql/", headers=headers, data=data)
            response_json = response.json()
            
            if response.ok:
                if response_json.get('data', {}).get('feedback_react') is None:
                    print(f"{Colors.RED}Không thể reaction - Bài viết không tồn tại hoặc bị chặn.{Colors.RESET}")
                    return False
                elif 'errors' in response_json:
                    print(f"{Colors.RED}Lỗi khi reaction: {response_json['errors'][0].get('message', 'Unknown error')}{Colors.RESET}")
                    return False
                else:
                    print(f"{Colors.GREEN}{reaction_name.upper()} reaction thành công!{Colors.RESET}")
                    return True
                    
            #print(f"{Colors.RED}Reaction thất bại. Status code: {response.status_code}{Colors.RESET}")
            return False
                
        except requests.RequestException as e:
            print(f"{Colors.RED}Lỗi kết nối khi thực hiện reaction: {e}{Colors.RESET}")
            return False

    def follow_user(self, target_id):
        variables = {
            "input": { "friend_requestee_ids": [target_id], "friending_channel": "PROFILE_BUTTON", "actor_id": self.account.uid }
        }
        headers = self.headers.copy()
        headers.update({'x-fb-friendly-name': 'FriendingCometFriendRequestSendMutation'})
        data = { "av": self.account.uid, "__user": self.account.uid, "fb_dtsg": self.account.fb_dtsg, "doc_id": "9088602351172612", "variables": json.dumps(variables) }
        try:
            response = requests.post("https://www.facebook.com/api/graphql/", headers=headers, data=data)
            if response and response.ok and 'errors' not in response.text:
                print(f"{Colors.GREEN}Đã gửi lời mời kết bạn/theo dõi thành công!{Colors.RESET}")
                return True
        except requests.RequestException as e:
            print(f"{Colors.RED}Lỗi kết nối khi follow: {e}{Colors.RESET}")
        print(f"{Colors.RED}Follow thất bại.{Colors.RESET}")
        return False

    def like_page(self, page_id):
        headers = self.headers.copy()
        headers.update({'referer': f'https://www.facebook.com/profile.php?id={page_id}', 'x-fb-friendly-name': 'CometProfilePlusLikeMutation'})
        variables = {"input": {"page_id": page_id, "actor_id": self.account.uid, "client_mutation_id": str(random.randint(1, 10))}, "scale": 1}
        data = { "av": self.account.uid, "__user": self.account.uid, "fb_dtsg": self.account.fb_dtsg, "jazoest": "25235", "lsd": "Yu3wpzhLqN-tpuB4S-pI-w", "variables": json.dumps(variables), "doc_id": "10062329867123540" }
        try:
            response = requests.post("https://www.facebook.com/api/graphql/", headers=headers, data=data)
            if response and response.ok and 'errors' not in response.text:
                print(f"{Colors.GREEN}Like page thành công!{Colors.RESET}")
                return True
        except requests.RequestException as e:
            print(f"{Colors.RED}Lỗi kết nối khi like page: {e}{Colors.RESET}")
        print(f"{Colors.RED}Like page thất bại. Response: {response.text[:200]}{Colors.RESET}")
        return False

class TDSClient:
    """Tương tác với API của TraoDoiSub.com (lấy job, nhận xu,...)."""
    def __init__(self, token):
        self.token = token
        self.cache_counters = {"facebook_follow_cache": 0, "facebook_page_cache": 0}

    def get_job_list(self, task_type):
        url = f"{TDS_FIELDS_URL}{task_type}&access_token={self.token}"
        try:
            response = requests.get(url)
            response.raise_for_status()
            result = response.json()
            if "data" in result and result["data"]:
                print(f"{Colors.GREEN}Đã tìm thấy {len(result['data'])} nhiệm vụ {task_type}.{Colors.RESET}")
                return result["data"]
            return []
        except (requests.RequestException, json.JSONDecodeError) as e:
            print(f"{Colors.RED}Lỗi khi lấy danh sách nhiệm vụ: {e}{Colors.RESET}")
            return []

    def _submit_for_reward(self, job_id, task_type):
        """Gửi yêu cầu nhận xu hoặc duyệt cho một nhiệm vụ và in ra response."""
        url = f"{TDS_COIN_URL}{task_type}&id={job_id}&access_token={self.token}"
        try:
            response = requests.get(url)
            # print(f"{Colors.PURPLE}[DEBUG TDS] URL: {url}{Colors.RESET}")
            # print(f"{Colors.PURPLE}[DEBUG TDS] Response Status: {response.status_code}{Colors.RESET}")
            # print(f"{Colors.PURPLE}[DEBUG TDS] Response Text: {response.text}{Colors.RESET}")
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"{Colors.RED}Lỗi kết nối khi gửi yêu cầu nhận xu: {e}{Colors.RESET}")
            return {"error": f"Request Error: {e}"}
        except json.JSONDecodeError:
            print(f"{Colors.RED}Lỗi: Response từ server TDS không phải là JSON hợp lệ.{Colors.RESET}")
            return {"error": "Invalid JSON response from TDS server"}

    def claim_reward(self, job_id, task_type):
        print(f"{Colors.YELLOW}Đang nhận xu cho Job ID: {job_id} (Type: {task_type}){Colors.RESET}")
        result = self._submit_for_reward(job_id, task_type)
        if result and "data" in result and result["data"].get("msg"):
            print(f"{Colors.GREEN}Thành công: {result['data']['msg']}{Colors.RESET}")
            print(f"{Colors.CYAN}Xu hiện tại: {result['data']['xu']}{Colors.RESET}")
            return True
        else:
            error_msg = result.get('error', 'Lỗi không xác định từ TDS.')
            print(f"{Colors.RED}Nhận xu thất bại: {error_msg}{Colors.RESET}")
            return False

    def submit_for_review(self, job_id, task_type):
        """
        Gửi nhiệm vụ vào hàng đợi duyệt và tự động nhận xu khi đủ.
        *** CẬP NHẬT: Sửa lỗi logic kiểm tra thành công ***
        """
        review_type = f"{task_type}_cache"
        print(f"{Colors.YELLOW}Đang gửi duyệt Job ID: {job_id}{Colors.RESET}")
        result = self._submit_for_reward(job_id, review_type)
        
        if result and result.get("msg") == "Thành công" and "cache" in result:
            current_cache_count = result["cache"]
            self.cache_counters[review_type] = current_cache_count
            print(f"{Colors.GREEN}Gửi duyệt thành công. Nhiệm vụ chờ duyệt ({task_type}): {current_cache_count}{Colors.RESET}")
            
            if current_cache_count >= 4:
                print(f"{Colors.YELLOW}Đủ {current_cache_count} nhiệm vụ, đang nhận xu hàng loạt cho '{task_type}'...{Colors.RESET}")
                batch_claimed = self.claim_reward(job_id, task_type)
                if batch_claimed:
                    self.cache_counters[review_type] = 0
            return True
        else:
            error_msg = result.get('error', 'Lỗi không xác định từ TDS.')
            print(f"{Colors.RED}Gửi duyệt thất bại: {error_msg}{Colors.RESET}")
            return False

# =========================================================================================
# SECTION: CÁC HÀM TIỆN ÍCH VÀ GIAO DIỆN (UTILITY & UI FUNCTIONS)
# =========================================================================================

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')
def init_colors():
    try:
        from colorama import init, Fore, Back, Style
        init(autoreset=True)
        return Fore, Back, Style
    except ImportError:
        # Fallback to ANSI codes if colorama not available
        class Colors:
            RED = '\033[91m'
            GREEN = '\033[92m'
            YELLOW = '\033[93m'
            BLUE = '\033[94m'
            MAGENTA = '\033[95m'
            CYAN = '\033[96m'
            WHITE = '\033[97m'
            ORANGE = '\033[38;5;208m'
            BRIGHT_GREEN = '\033[38;5;46m'
            BRIGHT_RED = '\033[38;5;196m'
            BRIGHT_YELLOW = '\033[38;5;226m'
            BRIGHT_CYAN = '\033[38;5;51m'
            RESET = '\033[0m'
            BOLD = '\033[1m'
            DIM = '\033[2m'
        
        return Colors, None, Colors
def print_banner():
    Fore, Back, Style = init_colors()
    
    # Clear screen
    os.system('cls' if os.name == 'nt' else 'clear')
    
    # Get random color scheme
    colors = get_random_color_scheme()
    reset_color = '\033[0m'
    
    # H-TOOL ASCII Art with random gradient colors
    print(f"""
{colors[0]}██╗  ██╗      {colors[1]}████████╗ ██████╗  ██████╗ ██╗     
{colors[0]}██║  ██║      {colors[1]}╚══██╔══╝██╔═══██╗██╔═══██╗██║     
{colors[1]}███████║█████╗{colors[2]}   ██║   ██║   ██║██║   ██║██║     
{colors[2]}██╔══██║╚════╝{colors[3]}   ██║   ██║   ██║██║   ██║██║     
{colors[2]}██║  ██║      {colors[3]}   ██║   ╚██████╔╝╚██████╔╝███████╗
{colors[3]}╚═╝  ╚═╝         ╚═╝    ╚═════╝  ╚═════╝ ╚══════╝{reset_color}
""")
    copyright_colors = ['\033[38;5;220m', '\033[38;5;226m', '\033[38;5;214m', '\033[38;5;208m']
    copyright_color = random.choice(copyright_colors)
    print(f"{copyright_color}                Copyright © H-Tool 2025 | Version 4.0{reset_color}")
    print()

def get_time_settings():
    print(f"\n{Colors.YELLOW}╔══════════════════════════════════════╗")
    print(f"║         THIẾT LẬP THỜI GIAN          ║")
    print(f"╚══════════════════════════════════════╝{Colors.RESET}")
    try:
        return {
            'delay_job': int(input(f"{Colors.CYAN}• Delay giữa các nhiệm vụ (giây): {Colors.RESET}")),
            'max_job_find': int(input(f"{Colors.CYAN}• Số lần tìm nhiệm vụ nếu không thấy: {Colors.RESET}")),
            'delay_find': int(input(f"{Colors.CYAN}• Delay mỗi lần tìm lại nhiệm vụ (giây): {Colors.RESET}")),
            'jobs_until_break': int(input(f"{Colors.CYAN}• Số nhiệm vụ trước khi nghỉ dài: {Colors.RESET}")),
            'break_time': int(input(f"{Colors.CYAN}• Thời gian nghỉ dài (giây): {Colors.RESET}")),
        }
    except ValueError:
        print(f"{Colors.RED}Vui lòng chỉ nhập số!{Colors.RESET}")
        return None

def select_task_types():
    print(f"\n{Colors.YELLOW}Chọn loại nhiệm vụ muốn thực hiện:{Colors.RESET}")
    for i, task in enumerate(SUPPORTED_TASK_TYPES, 1):
        print(f"{Colors.GREEN}{i}. {task}{Colors.RESET}")
    print(f"{Colors.CYAN}Lưu ý: Chọn nhiều bằng dấu + (VD: 1+3) hoặc 'all' để chọn tất cả.{Colors.RESET}")

    while True:
        choice = input(f"\n{Colors.BLUE}Nhập lựa chọn của bạn: {Colors.RESET}").lower().strip()
        if choice == 'all':
            return SUPPORTED_TASK_TYPES
        
        selected_tasks = []
        try:
            indices = [int(i.strip()) for i in choice.split('+')]
            for i in indices:
                if 1 <= i <= len(SUPPORTED_TASK_TYPES):
                    selected_tasks.append(SUPPORTED_TASK_TYPES[i-1])
                else:
                    raise IndexError
            return list(set(selected_tasks))
        except (ValueError, IndexError):
            print(f"{Colors.RED}Lựa chọn không hợp lệ. Vui lòng thử lại.{Colors.RESET}")

def select_facebook_accounts(valid_accounts):
    print(f"\n{Colors.YELLOW}Chọn tài khoản Facebook để chạy:{Colors.RESET}")
    for i, acc in enumerate(valid_accounts, 1):
        print(f"{Colors.GREEN}[{i}] {acc.name} - UID: {acc.uid}{Colors.RESET}")
    
    print(f"\n{Colors.CYAN}Cách chọn: Nhập số (1), nhiều số (1+3), khoảng (1-3) hoặc 'all'.{Colors.RESET}")
    
    while True:
        selection = input(f"{Colors.BLUE}Nhập lựa chọn: {Colors.RESET}").strip().lower()
        selected_indices = set()
        
        if selection == 'all':
            return valid_accounts
            
        try:
            parts = selection.split('+')
            for part in parts:
                if '-' in part:
                    start, end = map(int, part.split('-'))
                    selected_indices.update(range(start - 1, end))
                else:
                    selected_indices.add(int(part) - 1)
            
            return [valid_accounts[i] for i in sorted(list(selected_indices)) if 0 <= i < len(valid_accounts)]
        except (ValueError, IndexError):
            print(f"{Colors.RED}Lựa chọn không hợp lệ. Vui lòng thử lại.{Colors.RESET}")

# =========================================================================================
# SECTION: LOGIC CHÍNH CỦA TOOL (MAIN TOOL LOGIC)
# =========================================================================================

def run_jobs_for_account(tds_client: TDSClient, fb_account: FacebookAccount, task_types: list, time_settings: dict):
    fb_interactor = FacebookInteractor(fb_account)
    jobs_completed = 0
    find_job_attempts = 0
    jobs_since_break = 0
    
    print_banner()
    print(f"{Colors.PURPLE}--- Bắt đầu làm việc với tài khoản: {fb_account.name} ---{Colors.RESET}")

    while find_job_attempts < time_settings['max_job_find']:
        if jobs_since_break >= time_settings['jobs_until_break']:
            print(f"\n{Colors.YELLOW}Đã hoàn thành {jobs_since_break} nhiệm vụ. Nghỉ {time_settings['break_time']} giây...{Colors.RESET}")
            time.sleep(time_settings['break_time'])
            jobs_since_break = 0

        task_type = random.choice(task_types)
        print(f"\n{Colors.WHITE}Đang tìm nhiệm vụ loại: {Colors.BOLD}{task_type}{Colors.RESET}")
        
        jobs = tds_client.get_job_list(task_type)

        if not jobs:
            find_job_attempts += 1
            print(f"{Colors.YELLOW}Không có nhiệm vụ. Thử lại sau {time_settings['delay_find']}s (Lần {find_job_attempts}/{time_settings['max_job_find']}).{Colors.RESET}")
            time.sleep(time_settings['delay_find'])
            continue
        
        find_job_attempts = 0

        for job in jobs:
            if jobs_since_break >= time_settings['jobs_until_break']: break
            
            job_id = job['id']
            job_code = job.get('code', job_id)
            success = False
            
            print(f"\n{Colors.CYAN}--- Thực hiện Job ---")
            print(f"Time: {datetime.now().strftime('%H:%M:%S')} | Account: {fb_account.name} | Type: {task_type} | ID: {job_id}{Colors.RESET}")

            if task_type == "facebook_reaction":
                # *** CẬP NHẬT: Tự động xác định loại reaction từ job ***
                reaction_type_from_job = job.get('type', 'LIKE').upper()
                
                if reaction_type_from_job in REACTION_IDS:
                    print(f"{Colors.CYAN}--> Yêu cầu reaction: {reaction_type_from_job}{Colors.RESET}")
                    success = fb_interactor._perform_reaction(job_id, reaction_type_from_job)
                    if success:
                        tds_client.claim_reward(job_code, task_type)
                else:
                    print(f"{Colors.RED}Loại reaction không xác định từ job TDS: {reaction_type_from_job}{Colors.RESET}")
                    success = False

            elif task_type == "facebook_share":
                print(f"{Colors.YELLOW}Nhiệm vụ Share tạm thời bỏ qua vì API Facebook phức tạp và thay đổi thường xuyên.{Colors.RESET}")

            elif task_type == "facebook_follow":
                success = fb_interactor.follow_user(job_id)
                if success:
                    tds_client.submit_for_review(job_code, task_type)
            elif task_type == "facebook_page":
                success = fb_interactor.like_page(job_id)
                if success:
                    tds_client.submit_for_review(job_code, task_type)
            
            if success:
                jobs_completed += 1
                jobs_since_break += 1
                print(f"{Colors.BOLD}{Colors.GREEN}Tổng nhiệm vụ đã hoàn thành: {jobs_completed}{Colors.RESET}")

            print(f"{Colors.PURPLE}Delay {time_settings['delay_job']} giây trước khi làm nhiệm vụ tiếp theo...{Colors.RESET}")
            time.sleep(time_settings['delay_job'])

    print(f"\n{Colors.YELLOW}Đã đạt giới hạn tìm kiếm hoặc hoàn thành. Tổng số job đã làm cho tài khoản {fb_account.name}: {jobs_completed}{Colors.RESET}")

def login_tds():
    url = "https://traodoisub.com/scr/login.php"
    headers = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}
    
    while True:
        username = input(f"{Colors.BLUE}Nhập Tài Khoản TDS: {Colors.RESET}")
        password = input(f"{Colors.WHITE}Nhập Mật Khẩu TDS: {Colors.RESET}")
        data = {"username": username, "password": password}
        
        try:
            response = requests.post(url, headers=headers, data=data)
            response.raise_for_status()
            result = response.json()

            if result.get("success"):
                print(f"{Colors.GREEN}Đăng nhập TDS thành công!{Colors.RESET}")
                
                cookie_str = f"PHPSESSID={response.cookies.get('PHPSESSID')}"
                info_url = "https://traodoisub.com/view/setting/load.php"
                info_response = requests.post(info_url, headers={"Cookie": cookie_str})
                info_data = info_response.json()

                if "tokentds" in info_data:
                    print(f"{Colors.CYAN}User: {info_data.get('user', 'N/A')} | Xu: {info_data.get('xu', 'N/A')}{Colors.RESET}")
                    return TDSClient(info_data['tokentds'])
                else:
                    print(f"{Colors.RED}Không thể lấy token TDS.{Colors.RESET}")
            else:
                print(f"{Colors.RED}Đăng nhập thất bại: {result.get('error', 'Lỗi không xác định')}{Colors.RESET}")
        except (requests.RequestException, json.JSONDecodeError) as e:
            print(f"{Colors.RED}Lỗi khi đăng nhập TDS: {e}{Colors.RESET}")

def manage_cookies():
    saved_cookies_file = "saved_cookies.txt"
    while True:
        print(f"\n{Colors.PURPLE}Chọn cách cung cấp cookie Facebook:{Colors.RESET}")
        print(f"{Colors.GREEN}1: Nhập cookie trực tiếp{Colors.RESET}")
        print(f"{Colors.GREEN}2: Tải cookie từ file .txt{Colors.RESET}")
        print(f"{Colors.GREEN}3: Sử dụng cookie đã lưu từ lần trước{Colors.RESET}")
        choice = input(f"{Colors.BLUE}Nhập lựa chọn: {Colors.RESET}")

        cookies_str_list = []
        if choice == '1':
            cookie = input(f"{Colors.CYAN}Nhập cookie Facebook của bạn: {Colors.RESET}")
            if cookie: cookies_str_list.append(cookie)
        elif choice == '2':
            filename = input(f"{Colors.CYAN}Nhập tên file (VD: cookie.txt): {Colors.RESET}")
            try:
                with open(filename, 'r') as f:
                    cookies_str_list = [line.strip() for line in f if line.strip()]
            except FileNotFoundError:
                print(f"{Colors.RED}Không tìm thấy file {filename}{Colors.RESET}")
                continue
        elif choice == '3':
            try:
                with open(saved_cookies_file, 'r') as f:
                    cookies_str_list = [line.strip() for line in f if line.strip()]
                if not cookies_str_list:
                     print(f"{Colors.YELLOW}File cookie đã lưu bị trống.{Colors.RESET}")
                     continue
            except FileNotFoundError:
                print(f"{Colors.RED}Không có file cookie nào được lưu từ trước.{Colors.RESET}")
                continue
        else:
            print(f"{Colors.RED}Lựa chọn không hợp lệ.{Colors.RESET}")
            continue

        if not cookies_str_list:
            print(f"{Colors.YELLOW}Không có cookie nào được nhập.{Colors.RESET}")
            continue

        print(f"\n{Colors.YELLOW}Đang kiểm tra {len(cookies_str_list)} cookie...{Colors.RESET}")
        valid_accounts = []
        for cookie in cookies_str_list:
            account = FacebookAccount(cookie)
            if account.is_valid:
                valid_accounts.append(account)
                print(f"{Colors.GREEN}Hợp lệ: {account.name} - {account.uid}{Colors.RESET}")
            else:
                print(f"{Colors.RED}Không hợp lệ hoặc đã hết hạn.{Colors.RESET}")

        if valid_accounts:
            with open(saved_cookies_file, 'w') as f:
                f.write('\n'.join([acc.cookie for acc in valid_accounts]))
            print(f"{Colors.GREEN}Đã lưu {len(valid_accounts)} cookie hợp lệ vào '{saved_cookies_file}'{Colors.RESET}")
            return valid_accounts
        else:
            print(f"{Colors.RED}Không có cookie nào hợp lệ để chạy tool.{Colors.RESET}")

# =========================================================================================
# SECTION: ĐIỂM BẮT ĐẦU CHƯƠNG TRÌNH (ENTRY POINT)
# =========================================================================================
def get_random_color_scheme():
    """Tạo bộ màu ngẫu nhiên hài hòa"""
    color_schemes = [
        # Gradient Ocean Blue
        ['\033[38;5;33m', '\033[38;5;39m', '\033[38;5;45m', '\033[38;5;51m'],
        # Gradient Sunset
        ['\033[38;5;196m', '\033[38;5;202m', '\033[38;5;208m', '\033[38;5;214m'],
        # Gradient Purple Pink
        ['\033[38;5;129m', '\033[38;5;135m', '\033[38;5;141m', '\033[38;5;147m'],
        # Gradient Green Forest
        ['\033[38;5;22m', '\033[38;5;28m', '\033[38;5;34m', '\033[38;5;40m'],
        # Gradient Fire
        ['\033[38;5;124m', '\033[38;5;160m', '\033[38;5;196m', '\033[38;5;202m'],
        # Gradient Neon
        ['\033[38;5;46m', '\033[38;5;82m', '\033[38;5;118m', '\033[38;5;154m'],
        # Gradient Royal
        ['\033[38;5;54m', '\033[38;5;90m', '\033[38;5;126m', '\033[38;5;162m'],
        # Gradient Cyber
        ['\033[38;5;21m', '\033[38;5;27m', '\033[38;5;33m', '\033[38;5;39m'],
        # Gradient Warm
        ['\033[38;5;166m', '\033[38;5;172m', '\033[38;5;178m', '\033[38;5;184m'],
        # Gradient Cool
        ['\033[38;5;30m', '\033[38;5;36m', '\033[38;5;42m', '\033[38;5;48m']
    ]
    return random.choice(color_schemes)

def main():
    clear_screen()
    print_banner()

    tds_client = login_tds()
    if not tds_client:
        return

    while True:
        clear_screen()
        print_banner()
        
        valid_fb_accounts = manage_cookies()
        if not valid_fb_accounts:
            continue

        selected_fb_accounts = select_facebook_accounts(valid_fb_accounts)
        if not selected_fb_accounts:
            continue
            
        task_types = select_task_types()
        if not task_types:
            continue

        time_settings = get_time_settings()
        if not time_settings:
            continue
            
        for account in selected_fb_accounts:
            run_jobs_for_account(tds_client, account, task_types, time_settings)
            
            if len(selected_fb_accounts) > 1 and account != selected_fb_accounts[-1]:
                 another_run = input(f"\n{Colors.YELLOW}Chạy xong cho tài khoản {account.name}. Bạn có muốn tiếp tục với tài khoản tiếp theo? (y/n): {Colors.RESET}").lower()
                 if another_run != 'y':
                    break
            
        final_exit = input(f"\n{Colors.PURPLE}Tất cả các tài khoản đã chọn đã chạy xong. Bạn muốn thoát chương trình? (y/n): {Colors.RESET}").lower()
        if final_exit == 'y':
            break

    print(f"{Colors.BOLD}{Colors.GREEN}Cảm ơn bạn đã sử dụng tool!{Colors.RESET}")

if __name__ == "__main__":
    main()