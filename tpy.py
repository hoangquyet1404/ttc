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
        session_id = str(uuid.uuid4())
        timestamp = int(time.time())
        
        headers = {
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9',
            'content-type': 'application/x-www-form-urlencoded',
            'cookie': self.account.cookie,  # Fixed: Use account's cookie instead of self.cookie
            'origin': 'https://www.facebook.com',
            'priority': 'u=1, i',
            'referer': f'https://www.facebook.com/{post_id}',
            'sec-ch-ua': '"Brave";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
            'sec-ch-ua-full-version-list': '"Brave";v="137.0.0.0", "Chromium";v="137.0.0.0", "Not/A)Brand";v="24.0.0.0"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-model': '""',
            'sec-ch-ua-platform': '"Windows"',
            'sec-ch-ua-platform-version': '"15.0.0"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'sec-gpc': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
            'x-asbd-id': '359341',
            'x-fb-friendly-name': 'CometUFIFeedbackReactMutation',
            'x-fb-lsd': 'B1WQK7w_xB4eZAOvgT-tR-'
        }

        variables = {
            "input": {
                "attribution_id_v2": f"CometSinglePostDialogRoot.react,comet.post.single_dialog,via_cold_start,{timestamp}047,919959,,,",
                "feedback_id": feedback_id,
                "feedback_reaction_id": reaction_id,
                "feedback_source": "OBJECT",
                "is_tracking_encrypted": True,
                "tracking": None,
                "session_id": session_id,
                "actor_id": self.account.uid,
                "client_mutation_id": "1",
                "downstream_share_session_id": str(uuid.uuid4()),
                "downstream_share_session_origin_uri": f"https://www.facebook.com/{post_id}",
                "downstream_share_session_start_time": f"{timestamp}768"
            },
            "useDefaultActor": False,
            "__relay_internal__pv__CometUFIReactionsEnableShortNamerelayprovider": False
        }

        data = {
            "av": self.account.uid,
            "__aaid": "0",
            "__user": self.account.uid,
            "__a": "1", 
            "__req": "1i",
            "__hs": "20253.HYP:comet_pkg.2.1...0",
            "dpr": "1",
            "__ccg": "EXCELLENT",
            "__rev": "1023850259",
            "__s": "py7mo6:771bv2:5ra0tq",
            "__hsi": "7515788684770810449",
            "__comet_req": "15",
            "fb_dtsg": self.account.fb_dtsg,
            "jazoest": "25241",
            "lsd": "B1WQK7w_xB4eZAOvgT-tR-",
            "__spin_r": "1023850259",
            "__spin_b": "trunk",
            "__spin_t": str(timestamp),
            "fb_api_caller_class": "RelayModern",
            "fb_api_req_friendly_name": "CometUFIFeedbackReactMutation",
            "variables": json.dumps(variables),
            "server_timestamps": "true",
            "doc_id": "9518016021660044"
        }

        try:
            response = requests.post("https://www.facebook.com/api/graphql/", headers=headers, data=data)
            response_json = response.json()
            
            if response.ok and 'data' in response_json and response_json['data'].get('feedback_react'):
                print(f"{Colors.GREEN}{reaction_name.upper()} reaction thành công!{Colors.RESET}")
                return True
            else:
                print(f"{Colors.RED}{reaction_name.upper()} reaction thất bại.")
                print(f"Status Code: {response.status_code}")
                print(f"Response: {response.text[:200]}{Colors.RESET}")
                return False
                
        except requests.RequestException as e:
            print(f"{Colors.RED}Lỗi kết nối khi thực hiện reaction: {e}{Colors.RESET}")
            return False

    def follow_user(self, target_id):
        """Gửi lời mời kết bạn, nếu không được thì chuyển sang theo dõi."""
        timestamp = int(time.time())
        session_id = str(uuid.uuid4())

        # Common headers for both requests
        headers = {
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9',
            'content-type': 'application/x-www-form-urlencoded',
            'cookie': self.account.cookie,
            'origin': 'https://www.facebook.com',
            'priority': 'u=1, i',
            'referer': f'https://www.facebook.com/profile.php?id={target_id}',
            'sec-ch-ua': '"Brave";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
            'sec-ch-ua-full-version-list': '"Brave";v="137.0.0.0", "Chromium";v="137.0.0.0", "Not/A)Brand";v="24.0.0.0"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-model': '""',
            'sec-ch-ua-platform': '"Windows"',
            'sec-ch-ua-platform-version': '"15.0.0"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'sec-gpc': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
            'x-asbd-id': '359341',
            'x-fb-lsd': 'luH3GY4liovr25K3-Kmxnz'
        }

        try:
            # Try sending friend request first
            friend_headers = headers.copy()
            friend_headers.update({'x-fb-friendly-name': 'FriendingCometFriendRequestSendMutation'})
            
            friend_variables = {
                "input": {
                    "attribution_id_v2": f"ProfileCometContextualProfileRoot.react,comet.profile.contextual_profile,unexpected,{timestamp}710,151967,,,",
                    "friend_requestee_ids": [target_id],
                    "friending_channel": "PROFILE_BUTTON",
                    "warn_ack_for_ids": [],
                    "actor_id": self.account.uid,
                    "client_mutation_id": "7"
                },
                "scale": 1
            }

            friend_data = {
                "av": self.account.uid,
                "__user": self.account.uid,
                "__a": "1",
                "fb_dtsg": self.account.fb_dtsg,
                "variables": json.dumps(friend_variables),
                "doc_id": "9757269034400464"
            }

            friend_response = requests.post(
                "https://www.facebook.com/api/graphql/",
                headers=friend_headers,
                data=friend_data
            )

            # Check friend request response
            if friend_response.ok:
                friend_data = friend_response.json() if "application/json" in friend_response.headers.get('content-type', '').lower() else {}
                if not friend_data.get('errors'):
                    print(f"{Colors.GREEN}Đã gửi lời mời kết bạn thành công!{Colors.RESET}")
                    return True

            # If friend request fails or returns errors, try following
            print(f"{Colors.YELLOW}Chuyển sang thử theo dõi...{Colors.RESET}")
            
            follow_headers = headers.copy()
            follow_headers.update({'x-fb-friendly-name': 'CometUserFollowMutation'})

            follow_variables = {
                "input": {
                    "attribution_id_v2": f"ProfileCometTimelineListViewRoot.react,comet.profile.timeline.list,unexpected,{timestamp}313,397001,250100865708545,,",
                    "is_tracking_encrypted": False,
                    "subscribe_location": "PROFILE",
                    "subscribee_id": target_id,
                    "tracking": None,
                    "actor_id": self.account.uid,
                    "client_mutation_id": "11",
                    "session_id": session_id
                },
                "scale": 1
            }

            follow_data = {
                "av": self.account.uid,
                "__user": self.account.uid,
                "__a": "1",
                "fb_dtsg": self.account.fb_dtsg,
                "variables": json.dumps(follow_variables),
                "doc_id": "9831187040342850"
            }

            follow_response = requests.post(
                "https://www.facebook.com/api/graphql/",
                headers=follow_headers,
                data=follow_data
            )

            # Check follow response
            if follow_response.ok:
                follow_data = follow_response.json() if "application/json" in follow_response.headers.get('content-type', '').lower() else {}
                if not follow_data.get('errors'):
                    print(f"{Colors.GREEN}Đã theo dõi thành công!{Colors.RESET}")
                    return True
                else:
                    print(f"{Colors.RED}Không thể theo dõi. Lỗi: {follow_data.get('errors', ['Unknown error'])[0].get('message', 'Unknown error')}{Colors.RESET}")
            else:
                print(f"{Colors.RED}Không thể theo dõi. Status code: {follow_response.status_code}{Colors.RESET}")

            return False

        except requests.RequestException as e:
            print(f"{Colors.RED}Lỗi kết nối: {e}{Colors.RESET}")
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

    def share_post(self, task_id):
        """Thực hiện share bài viết theo API mới."""
        if '_' in task_id:
            post_id = task_id.split('_')[1]
        else:
            post_id = task_id
            
        current_time = int(time.time())
        
        headers = {
            "accept": "*/*",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "vi-VN,vi;q=0.9,fr-FR;q=0.8,fr;q=0.7,en-US;q=0.6,en;q=0.5",
            "content-type": "application/x-www-form-urlencoded",
            "cookie": self.account.cookie,
            "origin": "https://www.facebook.com",
            "priority": "u=1, i",
            "referer": "https://www.facebook.com/",
            "sec-ch-prefers-color-scheme": "light",
            "sec-ch-ua": '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
            "sec-ch-ua-full-version-list": '"Chromium";v="130.0.6723.92", "Google Chrome";v="130.0.6723.92", "Not?A_Brand";v="99.0.0.0"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-model": '""',
            "sec-ch-ua-platform": '"Windows"',
            "sec-ch-ua-platform-version": '"15.0.0"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "x-asbd-id": "129477",
            "x-fb-friendly-name": "ComposerStoryCreateMutation",
            "x-fb-lsd": "5tO9O8jtvQL-ScTarvAksW"
        }

        data = {
            "av": self.account.uid,
            "__aaid": "0",
            "__user": self.account.uid,
            "__a": "1",
            "__req": "33",
            "__hs": "20029.HYP:comet_pkg.2.1..2.1",
            "dpr": "1",
            "__ccg": "EXCELLENT",
            "__rev": "1017900723",
            "__s": "gqlros:g7edou:5h0uzz",
            "__hsi": "7432747778109978897",
            "__dyn": "7AzHK4HwBgDx-5Q1hyoyEqxd4Ag5S3G2O5U4e2C3-4UKewSAx-bwNwnof8boG4E762S1DwUx60xU8k1sw9u0LVEtwMw65xO2OU7m2210wEwgo9oO0wE7u12wOx62G5Usw9m1cwLwBgK7o8o4u0Mo4G1hx-3m1mzXw8W58jwGzEjzFU5e7oqBwJK14xm3y3aexfxmu3W3y2616DBx_wHwoE7u7EbXCwLyESE2KwwwOg2cwMwhA4UjyUaUcojxK2B0LwnU8oC1hxB0qo4e4UcEeE-3WVU-4EdrxG1fBG2-2K0UEmw",
            "__comet_req": "15",
            "fb_dtsg": self.account.fb_dtsg,
            "jazoest": "25217",
            "lsd": "5tO9O8jtvQL-ScTarvAksW",
            "__spin_r": "1017900723",
            "__spin_b": "trunk",
            "__spin_t": str(current_time),
            "fb_api_caller_class": "RelayModern",
            "fb_api_req_friendly_name": "ComposerStoryCreateMutation",
            "variables": json.dumps({
                "input": {
                    "composer_entry_point": "share_modal",
                    "composer_source_surface": "feed_story",
                    "composer_type": "share",
                    "idempotence_token": str(uuid.uuid4()) + "_FEED",
                    "source": "WWW",
                    "attachments": [{
                        "link": {
                            "share_scrape_data": json.dumps({
                                "share_type": 22,
                                "share_params": [post_id]
                            })
                        }
                    }],
                    "reshare_original_post": "RESHARE_ORIGINAL_POST",
                    "audience": {
                        "privacy": {
                            "allow": [],
                            "base_state": "EVERYONE",
                            "deny": [],
                            "tag_expansion_state": "UNSPECIFIED"
                        }
                    },
                    "message": {"ranges": [], "text": ""},
                    "actor_id": self.account.uid,
                    "client_mutation_id": "7"
                },
                "feedLocation": "NEWSFEED",
                "focusCommentID": None,
                "scale": 1,
                "privacySelectorRenderLocation": "COMET_STREAM",
                "renderLocation": "homepage_stream",
                "useDefaultActor": False,
                "isFeed": True
            }),
            "server_timestamps": True,
            "doc_id": "9502543119760740"
        }

        try:
            response = requests.post(
                "https://www.facebook.com/api/graphql/",
                headers=headers,
                data=data
            )
            
            try:
                # Try to parse first line of response as JSON
                first_line = response.text.split('\n')[0]
                response_json = json.loads(first_line)
                
                if response.ok and response_json.get('data', {}).get('story_create'):
                    #print(f"{Colors.GREEN}Share bài viết thành công!{Colors.RESET}")
                    return True
            except (json.JSONDecodeError, IndexError):
                pass
                
            print(f"{Colors.RED}Share thất bại. Status code: {response.status_code}{Colors.RESET}")
            return False
                
        except requests.RequestException as e:
            print(f"{Colors.RED}Lỗi kết nối khi share: {e}{Colors.RESET}")
            return False

class TDSClient:
    """Tương tác với API của TraoDoiSub.com (lấy job, nhận xu,...)."""
    def __init__(self, token):
        self.token = token
        self.cache_counters = {"facebook_follow_cache": 0, "facebook_page_cache": 0}
        # Map task types to their corresponding reward claim types
        self.claim_type_map = {
            "facebook_reaction": "facebook_reaction",
            "facebook_reaction2": "facebook_reaction2", 
            "facebook_reactioncmt": "facebook_reactioncmt",
            "facebook_share": "facebook_share",
            "facebook_follow": "facebook_follow",
            "facebook_page": "facebook_page"
        }

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
        """Gửi yêu cầu nhận xu hoặc duyệt cho một nhiệm vụ."""
        
        # Xử lý các trường hợp khác nhau cho job_id
        if task_type in ["facebook_follow", "facebook_page"]:
            # Khi nhận xu hàng loạt sau khi đủ cache
            claim_id = "facebook_api"
        elif task_type.endswith('_cache'):
            claim_id = job_id
        else:
            claim_id = job_id

        url = f"{TDS_COIN_URL}{task_type}&id={claim_id}&access_token={self.token}"
        
        try:
            # print(f"{Colors.PURPLE}[DEBUG TDS] Submitting request:")
            # print(f"URL: {url}")
            # print(f"Type: {task_type}")
            # print(f"ID/Code: {claim_id}{Colors.RESET}")
            
            response = requests.get(url)
            # print(f"{Colors.PURPLE}[DEBUG TDS] Response Status: {response.status_code}")
            # print(f"[DEBUG TDS] Response Text: {response.text}{Colors.RESET}")
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            print(f"{Colors.RED}Lỗi kết nối khi gửi yêu cầu nhận xu: {e}{Colors.RESET}")
            return {"error": f"Request Error: {e}"}
        except json.JSONDecodeError:
            print(f"{Colors.RED}Lỗi: Response từ server TDS không phải là JSON hợp lệ.{Colors.RESET}")
            return {"error": "Invalid JSON response from TDS server"}

    def claim_reward(self, job_id, task_type):
        """Nhận xu cho nhiệm vụ đã hoàn thành."""
        if task_type not in self.claim_type_map:
            print(f"{Colors.RED}Loại nhiệm vụ không hợp lệ: {task_type}{Colors.RESET}")
            return False

        claim_type = self.claim_type_map[task_type]
        #print(f"{Colors.YELLOW}Đang nhận xu cho Job ID: {job_id} (Type: {claim_type}){Colors.RESET}")
        result = self._submit_for_reward(job_id, claim_type)
        
        if result:
            if "error" in result:
                print(f"{Colors.RED}Nhận xu thất bại: {result['error']}{Colors.RESET}")
                return False
            elif "data" in result and result["data"].get("msg"):
                print(f"{Colors.GREEN}Thành công: {result['data']['msg']}{Colors.RESET}")
                print(f"{Colors.CYAN}Xu hiện tại: {result['data']['xu']}{Colors.RESET}")
                return True
            
        return False

    def submit_for_review(self, job_id, task_type):
        """Gửi nhiệm vụ vào hàng đợi duyệt và tự động nhận xu khi đủ."""
        if task_type not in ["facebook_follow", "facebook_page"]:
            print(f"{Colors.RED}Loại nhiệm vụ không hỗ trợ gửi duyệt: {task_type}{Colors.RESET}")
            return False
            
        review_type = f"{task_type}_cache"
        print(f"{Colors.YELLOW}Đang gửi duyệt Job ID: {job_id}{Colors.RESET}")
        result = self._submit_for_reward(job_id, review_type)
        
        if result and result.get("msg") == "Thành công" and "cache" in result:
            current_cache_count = result["cache"]
            self.cache_counters[review_type] = current_cache_count
            print(f"{Colors.GREEN}Gửi duyệt thành công. Nhiệm vụ chờ duyệt ({task_type}): {current_cache_count}{Colors.RESET}")
            
            if current_cache_count >= 4:
                print(f"{Colors.YELLOW}Đủ {current_cache_count} nhiệm vụ, đang nghỉ 3 giây trước khi nhận xu hàng loạt...{Colors.RESET}")
                time.sleep(3)  # Delay trước khi nhận xu hàng loạt
                # Gọi claim_reward với task_type gốc (không có _cache) và facebook_api làm ID
                batch_claimed = self.claim_reward('facebook_api', task_type)  
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

def print_banner():
    banner = f"""
{Colors.BOLD}{Colors.CYAN}╔══════════════════════════════════════════════════════════════╗
║                   TOOL TDS AUTO (CLEAN CODE)                  ║
║                  Coded by: Hoàng Dev & Gemini                 ║
║                     Version: 2.3.0 (Logic Fix)                       ║
╚══════════════════════════════════════════════════════════════╝{Colors.RESET}
"""
    print(banner)

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
                success = fb_interactor.share_post(job_id)
                if success:
                    #print(f"{Colors.YELLOW}Đợi 2 giây trước khi nhận xu...{Colors.RESET}")
                    time.sleep(2)  # Delay 2s before claiming reward
                    tds_client.claim_reward(job_code, task_type)
                    
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