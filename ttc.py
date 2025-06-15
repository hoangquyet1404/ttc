#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import requests
import json
import time
from datetime import datetime
import base64
import re
import uuid
import random
from bs4 import BeautifulSoup

# --- ANSI Color Codes for Terminal Output ---
_Black_ = '\033[1;30m'
_Red_ = '\033[1;31m'
_Green_ = '\033[1;32m'
_Yellow_ = '\033[1;33m'
_Blue_ = '\033[1;34m'
_Purple_ = '\033[1;35m'
_Cyan_ = '\033[1;36m'
_White_ = '\033[1;37m'
_Reset_ = '\033[0m'
_Bold_ = '\033[1m'
_Underline_ = '\033[4m'
_BgRed_ = '\033[41m'
_BgGreen_ = '\033[42m'
_BgYellow_ = '\033[43m'
_BgBlue_ = '\033[44m'
_BgPurple_ = '\033[45m'
_BgCyan_ = '\033[46m'

# --- Configuration ---

# Reaction types and their corresponding GraphQL IDs for Facebook
REACTION_TYPES = {
    "LIKE": "1635855486666999",
    "LOVE": "1678524932434102",
    "CARE": "613557422527858",
    "HAHA": "115940658764963",
    "WOW": "478547315650144",
    "SAD": "908563459236466",
    "ANGRY": "444813342392137"
}

# Default settings for delays and breaks to avoid getting blocked.
DEFAULT_SETTINGS = {
    'DELAY_BETWEEN_JOBS': (3, 7),      # (min, max) seconds between jobs
    'JOBS_BEFORE_BREAK': 15,           # Number of jobs to complete before a short break
    'BREAK_TIME': (300, 600),          # (min, max) seconds for a short break (5-10 minutes)
    'JOBS_BEFORE_LONG_BREAK': 50,      # Number of jobs to complete before a long break
    'LONG_BREAK_TIME': (900, 1800),    # (min, max) seconds for a long break (15-30 minutes)
    'JOBS_BEFORE_SWITCH': 10,          # Number of jobs before switching account
}

# ==============================================================================
# SECTION: TUONGTACCHEO API INTERACTION
# ==============================================================================

def login_ttc(username, password):
    """Logs into TuongTacCheo and returns session cookies."""
    login_url = "https://tuongtaccheo.com/login.php"
    login_data = {
        "username": username,
        "password": password,
        "submit": "ĐĂNG NHẬP"
    }
    session = requests.Session()
    try:
        response = session.post(login_url, data=login_data)
        response.raise_for_status()
        if "success" in response.text.lower():
            return session.cookies.get_dict()
    except requests.RequestException as e:
        print(f"{_Red_}Lỗi khi đăng nhập TTC: {e}{_Reset_}")
    return None

def get_ttc_token(cookies):
    """Fetches the TTC access token from the API page."""
    api_url = "https://tuongtaccheo.com/api/"
    try:
        response = requests.get(api_url, cookies=cookies)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        token_input = soup.find('input', {'name': 'ttc_access_token'})
        if token_input:
            return token_input.get('value')
    except requests.RequestException as e:
        print(f"{_Red_}Lỗi khi lấy TTC token: {e}{_Reset_}")
    return None

def get_account_info(token):
    """Fetches TTC account details (user, balance) using the token."""
    info_url = "https://tuongtaccheo.com/logintoken.php"
    data = {"access_token": token}
    try:
        response = requests.post(info_url, data=data)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"{_Red_}Lỗi khi lấy thông tin tài khoản TTC: {e}{_Reset_}")
    except json.JSONDecodeError:
        print(f"{_Red_}Phản hồi không hợp lệ từ server TTC.{_Reset_}")
    return {}

def _fetch_jobs_from_endpoint(url, cookies):
    """Generic function to fetch jobs from a TTC endpoint."""
    headers = {"X-Requested-With": "XMLHttpRequest"}
    try:
        response = requests.get(url, headers=headers, cookies=cookies)
        response.raise_for_status()
        if response.text in ["0", "[]"]:  # API returns these for no jobs
            return []
        # Convert string responses to dictionaries if needed
        jobs = response.json()
        if isinstance(jobs, str):
            jobs = [{"idpost": jobs}]  # Wrap single job ID in a dictionary
        elif isinstance(jobs, list) and jobs and isinstance(jobs[0], str):
            jobs = [{"idpost": job} for job in jobs]  # Convert list of IDs to list of dictionaries
        return jobs
    except requests.RequestException as e:
        print(f"{_Red_}Lỗi kết nối tới {url}: {e}{_Reset_}")
    except json.JSONDecodeError:
        pass  # Non-json response usually means no jobs
    return []

# def get_reaction_jobs(cookies):
#     """Fetches standard reaction jobs from TTC."""
#     return _fetch_jobs_from_endpoint("https://tuongtaccheo.com/kiemtien/camxuccheo/getpost.php", cookies)

def get_vip_reaction_jobs(cookies):
    """Fetches VIP reaction jobs from TTC."""
    return _fetch_jobs_from_endpoint("https://tuongtaccheo.com/kiemtien/camxucvipcheo/getpost.php", cookies)

def get_vip_re_reaction_jobs(cookies):
    """Fetches VIP-RE reaction jobs from TTC."""
    return _fetch_jobs_from_endpoint("https://tuongtaccheo.com/kiemtien/camxucvipre/getpost.php", cookies)

def get_follow_jobs(cookies):
    """Fetches available follow jobs from TTC."""
    return _fetch_jobs_from_endpoint("https://tuongtaccheo.com/kiemtien/subcheo/getpost.php", cookies)

def get_share_jobs(cookies):
    """Fetches available share jobs from TTC."""
    return _fetch_jobs_from_endpoint("https://tuongtaccheo.com/kiemtien/sharecheo/getpost.php", cookies)


def claim_reaction_reward(cookies, post_id, reaction_type, job_type="normal"):
    """Claims the reward for a completed reaction job."""
    # Different endpoints for different reaction types
    endpoints = {
        # "normal": "https://tuongtaccheo.com/kiemtien/camxuccheo/nhantien.php",
        "vip": "https://tuongtaccheo.com/kiemtien/camxucvipcheo/nhantien.php",
        "vip_re": "https://tuongtaccheo.com/kiemtien/camxucvipre/nhantien.php"
    }
    
    claim_url = endpoints.get(job_type, endpoints["vip"])
    referer_url = claim_url.replace("nhantien.php", "")
    
    headers = {
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9",
        "content-type": "application/x-www-form-urlencoded",
        "origin": "https://tuongtaccheo.com",
        "priority": "u=1, i",
        "referer": referer_url,
        "sec-ch-ua": '"Microsoft Edge";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36 Edg/137.0.0.0",
        "x-requested-with": "XMLHttpRequest"
    }

    data = {
        "id": post_id,
        "loaicx": reaction_type
    }

    try:
        response = requests.post(
            claim_url, 
            headers=headers, 
            cookies=cookies, 
            data=data,
            timeout=10
        )
        response.raise_for_status()
        
        if response.ok:
            try:
                result = response.json()
                if result and isinstance(result, dict):
                    return result
                print(f"{_Red_}Server trả về dữ liệu không hợp lệ: {response.text}{_Reset_}")
            except json.JSONDecodeError:
                print(f"{_Red_}Không thể parse JSON từ response: {response.text}{_Reset_}")
        else:
            print(f"{_Red_}Server trả về status code: {response.status_code}{_Reset_}")
            
    except requests.RequestException as e:
        print(f"{_Red_}Lỗi khi nhận thưởng reaction: {str(e)}{_Reset_}")
        if hasattr(e, 'response') and e.response:
            print(f"{_Red_}Response from server: {e.response.text}{_Reset_}")
    
    return None

def claim_follow_reward(cookies, target_id):
    """Claims the reward for a completed follow job."""
    claim_url = "https://tuongtaccheo.com/kiemtien/subcheo/nhantien.php"
    referer_url = claim_url.replace("nhantien.php", "")
    
    headers = {
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9",
        "content-type": "application/x-www-form-urlencoded",
        "origin": "https://tuongtaccheo.com",
        "priority": "u=1, i",
        "referer": referer_url,
        "sec-ch-ua": '"Microsoft Edge";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36 Edg/137.0.0.0",
        "x-requested-with": "XMLHttpRequest"
    }

    data = {"id": target_id}

    try:
        response = requests.post(
            claim_url, 
            headers=headers, 
            cookies=cookies, 
            data=data,
            timeout=10
        )
        response.raise_for_status()
        
        if response.ok:
            try:
                result = response.json()
                if result and isinstance(result, dict):
                    return result
                print(f"{_Red_}Server trả về dữ liệu không hợp lệ: {response.text}{_Reset_}")
            except json.JSONDecodeError:
                print(f"{_Red_}Không thể parse JSON từ response: {response.text}{_Reset_}")
        else:
            print(f"{_Red_}Server trả về status code: {response.status_code}{_Reset_}")
            
    except requests.RequestException as e:
        print(f"{_Red_}Lỗi khi nhận thưởng follow: {str(e)}{_Reset_}")
        if hasattr(e, 'response') and e.response:
            print(f"{_Red_}Response from server: {e.response.text}{_Reset_}")
    
    return None

def claim_share_reward(cookies, post_id):
    """Claims the reward for a completed share job."""
    claim_url = "https://tuongtaccheo.com/kiemtien/sharecheo/nhantien.php"
    referer_url = claim_url.replace("nhantien.php", "")
    
    headers = {
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9",
        "content-type": "application/x-www-form-urlencoded", 
        "origin": "https://tuongtaccheo.com",
        "referer": referer_url,
        "x-requested-with": "XMLHttpRequest"
    }

    data = {"id": post_id}

    try:
        response = requests.post(
            claim_url,
            headers=headers,
            cookies=cookies,
            data=data,
            timeout=10
        )
        response.raise_for_status()
        
        if response.ok:
            try:
                result = response.json()
                if result and isinstance(result, dict):
                    return result
            except json.JSONDecodeError:
                pass
    except Exception as e:
        print(f"{_Red_}Lỗi khi nhận thưởng share: {str(e)}{_Reset_}")
    
    return None

# ==============================================================================
# SECTION: FACEBOOK INTERACTION
# ==============================================================================

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
                print(f"{_Red_}Cookie không hợp lệ: Thiếu 'c_user'.{_Reset_}")
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
                print(f"{_Red_}Không thể truy cập Facebook (Status: {response.status_code}).{_Reset_}")
                return False

            fb_dtsg_match = re.search(r'"DTSGInitialData",\[\],{"token":"(.*?)"', response.text) or \
                            re.search(r'name="fb_dtsg" value="(.*?)"', response.text) or \
                            re.search(r'"async_get_token":"(.*?)"', response.text)

            if not fb_dtsg_match:
                print(f"{_Red_}Không thể lấy fb_dtsg. Cookie có thể đã hết hạn.{_Reset_}")
                return False
            self.fb_dtsg = fb_dtsg_match.group(1)

            name_match = re.search(r'"NAME":"(.*?)"', response.text)
            if name_match:
                # Decode unicode escape sequences like \u00E0
                self.name = name_match.group(1).encode('utf-8').decode('unicode-escape')
            else:
                # Fallback to mbasic if NAME not found
                mbasic_response = requests.get(f'https://mbasic.facebook.com/profile.php?id={self.uid}', headers=headers)
                self.name = mbasic_response.text.split('<title>')[1].split('</title>')[0]

            return True

        except Exception as e:
            print(f"{_Red_}Lỗi khi lấy thông tin Facebook: {str(e)}{_Reset_}")
            return False

class FacebookInteractor:
    """Thực hiện tất cả các hành động tương tác với Facebook (share, reaction, follow, page like)."""
    def __init__(self, fb_account: FacebookAccount):
        self.account = fb_account
        self.base_headers = {
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9",
            "content-type": "application/x-www-form-urlencoded",
            "cookie": self.account.cookie,
            "origin": "https://www.facebook.com",
            "priority": "u=1, i",
            "sec-ch-ua": '"Brave";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
            "sec-ch-ua-full-version-list": '"Brave";v="137.0.0.0", "Chromium";v="137.0.0.0", "Not/A)Brand";v="24.0.0.0"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-model": '""',
            "sec-ch-ua-platform": '"Windows"',
            "sec-ch-ua-platform-version": '"15.0.0"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "sec-gpc": "1",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
            "x-asbd-id": "359341",
            "x-fb-friendly-name": "CometUFIFeedbackReactMutation",
            "x-fb-lsd": "SaEkSywP_uH8A3cpczP2RG"
        }

    def _get_post_id(self, task_id):
        return task_id.split('_')[1] if '_' in task_id else task_id

    def react_to_post(self, post_id, reaction_name):
        """Thực hiện một reaction cụ thể."""
        reaction_id = REACTION_TYPES.get(reaction_name.upper())
        if not reaction_id:
            return False

        timestamp = int(time.time())
        session_id = str(uuid.uuid4())
        downstream_id = str(uuid.uuid4())
        
        feedback_id = base64.b64encode(f"feedback:{post_id}".encode()).decode()
        
        variables = {
            "input": {
                "attribution_id_v2": f"CometHomeRoot.react,comet.home,unexpected,{timestamp}218,293778,4748854339,,;CometTahoeRoot.react,comet.videos.tahoe,via_cold_start,{timestamp}036,852242,2392950137,13#301,",
                "feedback_id": feedback_id,
                "feedback_reaction_id": reaction_id,
                "feedback_source": "NEWS_FEED",
                "is_tracking_encrypted": True,
                "tracking": None,
                "session_id": session_id,
                "actor_id": self.account.uid,
                "client_mutation_id": "1",
                "downstream_share_session_id": downstream_id,
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
            "__req": "2j",
            "__hs": "20253.HYP:comet_pkg.2.1...0",
            "dpr": "1",
            "__ccg": "EXCELLENT",
            "__rev": "1023850259",
            "__s": "gq5886:771bv2:ktsyaf",
            "__hsi": "7515817998251305179",
            "__comet_req": "15",
            "fb_dtsg": self.account.fb_dtsg,
            "jazoest": "25478",
            "lsd": self.base_headers["x-fb-lsd"],
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
            response = requests.post(
                "https://www.facebook.com/api/graphql/",
                headers=self.base_headers,
                data=data,
                timeout=10
            )
            response.raise_for_status()
            
            if response.ok and 'errors' not in response.text:
                return True
            return False
                
        except requests.RequestException:
            return False

    def follow_user(self, target_id):
        """Gửi lời mời kết bạn hoặc theo dõi."""
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
                    return True

            # Try following without messages
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
                return not follow_data.get('errors')
            return False
        except:
            return False

    def share_post(self, post_id):
        """Shares a Facebook post."""
        timestamp = int(time.time())
        
        headers = {
            "accept": "*/*",
            "accept-language": "vi-VN,vi;q=0.9,fr-FR;q=0.8,fr;q=0.7,en-US;q=0.6,en;q=0.5",
            "content-type": "application/x-www-form-urlencoded",
            "cookie": self.account.cookie,
            "origin": "https://www.facebook.com",
            "priority": "u=1, i",
            "referer": "https://www.facebook.com/",
            "sec-ch-ua": '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
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
            "__spin_t": str(timestamp),
            "fb_api_caller_class": "RelayModern",
            "fb_api_req_friendly_name": "ComposerStoryCreateMutation",
            "variables": json.dumps({
                "input": {
                    "composer_entry_point": "share_modal",
                    "composer_source_surface": "feed_story",
                    "composer_type": "share",
                    "idempotence_token": f"{str(uuid.uuid4())}_FEED",
                    "source": "WWW",
                    "attachments": [{
                        "link": {
                            "share_scrape_data": json.dumps({
                                "share_type": 22,
                                "share_params": [str(post_id)]
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
                data=data,
                timeout=10
            )
            response.raise_for_status()
            
            if response.ok and 'errors' not in response.text:
                print(f"{_Green_}Đã chia sẻ thành công bài viết {post_id}{_Reset_}")
                return True
                
            error_msg = response.json().get('errors', [{}])[0].get('message', 'Unknown error')
            # print(f"{_Red_}Không thể chia sẻ bài viết {post_id}: {error_msg}{_Reset_}")
            return False
                
        except Exception as e:
            print(f"{_Red_}Lỗi khi chia sẻ bài viết: {str(e)}{_Reset_}")
            return False

# ==============================================================================
# SECTION: JOB PROCESSING LOGIC
# ==============================================================================

def extract_xu_from_message(message):
    """Extracts xu amount from success message."""
    if not message:
        return "???"
    xu_match = re.search(r'cộng (\d+) xu', message)
    return xu_match.group(1) if xu_match else "???"

def countdown_display(seconds):
    """Displays countdown timer on console."""
    for i in range(int(seconds), 0, -1):
        print(f"{_Cyan_}Chờ {i}s cho job tiếp theo...{_Reset_}", end='\r')
        time.sleep(1)
    print(" " * 50, end='\r')  # Clear the line

def process_reaction_job(job, interactor: FacebookInteractor, cookies, settings):
    """Processes a single reaction job."""
    ttc_post_id = job['idpost']
    fb_post_id = job.get('idfb')
    
    if not fb_post_id or not job.get('loaicx'):
        return (None, 2)
    
    # Fix job type detection
    if isinstance(job.get("link", ""), str):
        if "camxucvipcheo" in job.get("link", ""):
            job_type = "vip"
        elif "camxucvipre" in job.get("link", ""):
            job_type = "vip_re"
        else:
            job_type = "normal"
    else:
        # For VIP-RE jobs that come from getpost.php directly
        job_type = "vip_re" if job.get('type') == "reaction" else "normal"
    
    reaction_type = job.get('loaicx') or job.get('type_react')
    
    if interactor.react_to_post(fb_post_id, reaction_type):
        time.sleep(random.uniform(2, 4))
        
        try:
            result = claim_reaction_reward(cookies, ttc_post_id, reaction_type, job_type)
            
            if result:
                xu_amount = extract_xu_from_message(result.get('mess', ''))
                delay = random.uniform(*settings['DELAY_BETWEEN_JOBS'])
                print(f"{_Green_}[{datetime.now().strftime('%H:%M:%S')}] {interactor.account.name}|REACTION:{reaction_type}|{job_type}|{fb_post_id}|+{xu_amount} xu| {delay:.1f}s{_Reset_}")
                countdown_display(delay)
                return (result, delay)
            
            return ({'status': 'success', 'mess': 'Reaction completed', 'sodu': '???'}, 2)
            
        except Exception as e:
            print(f"{_Red_}Lỗi: {str(e)}{_Reset_}")
            return (None, 2)
    
    print(f"{_Red_}[{datetime.now().strftime('%H:%M:%S')}] {interactor.account.name}|REACTION:{reaction_type}|{job_type}|{fb_post_id}|Bài viết không tồn tại{_Reset_}")
    return (None, 2)

def process_follow_job(job, interactor: FacebookInteractor, cookies, settings):
    """Processes a single follow job."""
    target_id = job['idpost']
    
    if not target_id:
        return (None, 2)
    
    try:
        follow_success = interactor.follow_user(target_id)
        time.sleep(random.uniform(2, 4))
        
        result = claim_follow_reward(cookies, target_id)
        
        if result and ('xu' in str(result).lower() or result.get('status') == 'success'):
            delay = random.uniform(*settings['DELAY_BETWEEN_JOBS'])
            xu_amount = extract_xu_from_message(result.get('mess', ''))
            print(f"{_Green_}[{datetime.now().strftime('%H:%M:%S')}] {interactor.account.name}|FOLLOW|normal|{target_id}|+{xu_amount} xu| {delay:.1f}s{_Reset_}")
            countdown_display(delay)
            return (result, delay)
            
        if not follow_success and not result:
            print(f"{_Red_}[{datetime.now().strftime('%H:%M:%S')}] {interactor.account.name}|FOLLOW|normal|{target_id}|Không thể theo dõi{_Reset_}")
            
    except Exception as e:
        print(f"{_Red_}Lỗi khi thực hiện follow: {str(e)}{_Reset_}")
    
    return (None, 2)

def process_share_job(job, interactor: FacebookInteractor, cookies, settings):
    """Processes a single share job."""
    if not job.get('link') or not job.get('idpost'):
        return (None, 2)
        
    try:
        link = job['link']
        try:
            post_id = link.split('facebook.com/')[1].split('_')[0]
        except:
            try:
                post_id = link.split('/posts/')[1].split('?')[0].strip('/')
            except:
                post_id = job['idpost']
        
        if not post_id:
            return (None, 2)
        
        share_success = interactor.share_post(post_id)
        time.sleep(random.uniform(2, 4))
        
        # Use the original idpost for claiming reward
        result = claim_share_reward(cookies, job['idpost'])
        
        if result and ('xu' in str(result).lower() or result.get('status') == 'success'):
            delay = random.uniform(*settings['DELAY_BETWEEN_JOBS'])
            xu_amount = extract_xu_from_message(result.get('mess', ''))
            print(f"{_Green_}[{datetime.now().strftime('%H:%M:%S')}] {interactor.account.name}|SHARE|normal|{post_id}|+{xu_amount} xu| {delay:.1f}s{_Reset_}")
            countdown_display(delay)
            return (result, delay)
            
        if not share_success:
            print(f"{_Red_}[{datetime.now().strftime('%H:%M:%S')}] {interactor.account.name}|SHARE|normal|{post_id}|Không phải là bài viết or không tồn tại{_Reset_}")
            
    except Exception as e:
        print(f"{_Red_}Lỗi khi thực hiện share cho bài viết {job.get('idpost')}: {str(e)}{_Reset_}")
    
    return (None, 2)

# ==============================================================================
# SECTION: UI & MAIN EXECUTION
# ==============================================================================
def get_random_color_scheme():
    """Tạo bộ màu ngẫu nhiên hài hòa"""
    color_schemes = [
        ['\033[38;5;33m', '\033[38;5;39m', '\033[38;5;45m', '\033[38;5;51m'],
        ['\033[38;5;196m', '\033[38;5;202m', '\033[38;5;208m', '\033[38;5;214m'],
        ['\033[38;5;129m', '\033[38;5;135m', '\033[38;5;141m', '\033[38;5;147m'],
        ['\033[38;5;22m', '\033[38;5;28m', '\033[38;5;34m', '\033[38;5;40m'],
        ['\033[38;5;124m', '\033[38;5;160m', '\033[38;5;196m', '\033[38;5;202m'],
        ['\033[38;5;46m', '\033[38;5;82m', '\033[38;5;118m', '\033[38;5;154m'],
        ['\033[38;5;54m', '\033[38;5;90m', '\033[38;5;126m', '\033[38;5;162m'],
        ['\033[38;5;21m', '\033[38;5;27m', '\033[38;5;33m', '\033[38;5;39m'],
        ['\033[38;5;166m', '\033[38;5;172m', '\033[38;5;178m', '\033[38;5;184m'],
        ['\033[38;5;30m', '\033[38;5;36m', '\033[38;5;42m', '\033[38;5;48m']
    ]
    return random.choice(color_schemes)
def print_banner():
    Fore, Back, Style = init_colors()
    os.system('cls' if os.name == 'nt' else 'clear')
    colors = get_random_color_scheme()
    reset_color = '\033[0m'
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

def print_section(title):
    """Prints a formatted section header."""
    print(f"\n{_Bold_}{_Purple_}>> {title.upper()} <<{_Reset_}")

def setup_settings():
    """Allows user to customize delay and break settings."""
    print_section("Thiết Lập Cấu Hình")
    settings = DEFAULT_SETTINGS.copy()
    try:
        print("Thiết lập delay giữa các job (Nhấn Enter để dùng mặc định):")
        min_delay = input(f"- Delay tối thiểu ({DEFAULT_SETTINGS['DELAY_BETWEEN_JOBS'][0]}s): ") or DEFAULT_SETTINGS['DELAY_BETWEEN_JOBS'][0]
        max_delay = input(f"- Delay tối đa ({DEFAULT_SETTINGS['DELAY_BETWEEN_JOBS'][1]}s): ") or DEFAULT_SETTINGS['DELAY_BETWEEN_JOBS'][1]
        settings['DELAY_BETWEEN_JOBS'] = (int(min_delay), int(max_delay))
        
        print("\nThiết lập đổi tài khoản:")
        jobs_switch = input(f"- Số job trước khi đổi account ({DEFAULT_SETTINGS['JOBS_BEFORE_SWITCH']}): ") or DEFAULT_SETTINGS['JOBS_BEFORE_SWITCH']
        settings['JOBS_BEFORE_SWITCH'] = int(jobs_switch)
    except ValueError:
        print(f"{_Red_}Nhập không hợp lệ, sử dụng cài đặt mặc định.{_Reset_}")
        return DEFAULT_SETTINGS
    return settings

def select_accounts(accounts):
    """Allows user to select which accounts to use."""
    print_section("Chọn tài khoản Facebook để chạy job")
    for i, account in enumerate(accounts, 1):
        print(f"{i}. {account.name} (UID: {account.uid})")
    print(f"all. Chọn tất cả tài khoản")
    
    choice = input(f"\n{_Yellow_}Nhập số thứ tự tài khoản (phân cách bằng dấu +, ví dụ: 1+2+3): {_Reset_}")
    
    if choice.lower() == 'all':
        return accounts
        
    try:
        selected_indices = [int(x.strip()) - 1 for x in choice.split('+')]
        selected_accounts = [accounts[i] for i in selected_indices if 0 <= i < len(accounts)]
        if not selected_accounts:
            print(f"{_Red_}Không có tài khoản nào được chọn, sử dụng tất cả.{_Reset_}")
            return accounts
        return selected_accounts
    except (ValueError, IndexError):
        print(f"{_Red_}Lựa chọn không hợp lệ, sử dụng tất cả tài khoản.{_Reset_}")
        return accounts

def load_and_validate_cookies():
    """Loads cookies from cookie.txt and validates them."""
    accounts = []
    if not os.path.exists("cookie.txt"):
        return accounts
        
    print_section("Đang kiểm tra cookie.txt")
    with open("cookie.txt", "r", encoding="utf-8") as f:
        saved_cookies = f.read().strip().split("|")
        for i, cookie_str in enumerate(saved_cookies):
            if cookie_str.strip():
                print(f"Đang kiểm tra cookie #{i+1}...")
                fb_account = FacebookAccount(cookie_str.strip())
                if fb_account.is_valid:
                    accounts.append(fb_account)
                    print(f"{_Green_} -> Hợp lệ: {fb_account.name} (UID: {fb_account.uid}){_Reset_}")
                else:
                    print(f"{_Red_} -> Không hợp lệ hoặc đã hết hạn.{_Reset_}")
    return accounts

def load_cookies_from_input():
    """Loads Facebook cookies from user input or file."""
    print("\nChọn cách nhập cookie Facebook:")
    print("1. Nhập cookie trực tiếp (Enter để bỏ qua)")
    print("2. Nhập cookie từ file (mỗi cookie một dòng)")
    
    choice = input(f"{_Yellow_}Lựa chọn của bạn (1/2): {_Reset_}")
    
    if choice == "1":
        cookie = input(f"{_Yellow_}Nhập cookie Facebook (Enter để bỏ qua): {_Reset_}")
        if cookie.strip():
            return [cookie.strip()]
    elif choice == "2":
        filename = input(f"{_Yellow_}Nhập tên file chứa cookie: {_Reset_}")
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return [line.strip() for line in f if line.strip()]
        except Exception as e:
            print(f"{_Red_}Lỗi khi đọc file: {str(e)}{_Reset_}")
    
    return []
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

def load_saved_accounts():
    """Loads saved TTC accounts from account.txt"""
    accounts = []
    try:
        with open("account.txt", "r", encoding="utf-8") as f:
            for line in f:
                if '|' in line:
                    username, password = line.strip().split('|')
                    accounts.append({"username": username, "password": password})
    except FileNotFoundError:
        return []
    return accounts

def save_account(username, password):
    """Saves TTC account credentials to account.txt"""
    try:
        with open("account.txt", "a", encoding="utf-8") as f:
            f.write(f"{username}|{password}\n")
        print(f"{_Green_}Đã lưu thông tin tài khoản vào account.txt{_Reset_}")
    except Exception as e:
        print(f"{_Red_}Lỗi khi lưu tài khoản: {str(e)}{_Reset_}")

def select_saved_account():
    """Allows user to select a saved TTC account"""
    accounts = load_saved_accounts()
    if not accounts:
        print(f"{_Red_}Không tìm thấy tài khoản đã lưu trong account.txt{_Reset_}")
        return None, None

    print("\nDanh sách tài khoản đã lưu:")
    for i, acc in enumerate(accounts, 1):
        print(f"{i}. {acc['username']}")

    try:
        choice = int(input(f"\n{_Yellow_}Chọn tài khoản (1-{len(accounts)}): {_Reset_}"))
        if 1 <= choice <= len(accounts):
            selected = accounts[choice-1]
            return selected["username"], selected["password"]
    except (ValueError, IndexError):
        print(f"{_Red_}Lựa chọn không hợp lệ{_Reset_}")
    return None, None

def ttc_login_menu():
    """Displays TTC login menu and handles login process"""
    print_section("Đăng nhập TuongTacCheo")
    print("1. Đăng nhập tài khoản mới")
    print("2. Sử dụng tài khoản đã lưu")
    
    choice = input(f"\n{_Yellow_}Lựa chọn của bạn (1-2): {_Reset_}")
    
    if choice == "1":
        username = input(f"{_Yellow_}Nhập username TTC: {_Reset_}")
        password = input(f"{_Yellow_}Nhập password TTC: {_Reset_}")
        cookies = login_ttc(username, password)
        if cookies:
            save_account(username, password)
            return cookies
    elif choice == "2":
        username, password = select_saved_account()
        if username and password:
            return login_ttc(username, password)
    else:
        print(f"{_Red_}Lựa chọn không hợp lệ{_Reset_}")
    
    return None

def main():
    """Main function to run the tool."""
    print_banner()
    
    # 1. Login to TTC using new menu
    ttc_cookies = ttc_login_menu()
    if not ttc_cookies:
        print(f"{_Red_}Đăng nhập TTC thất bại. Vui lòng kiểm tra lại.{_Reset_}")
        return
    print(f"{_Green_}Đăng nhập TTC thành công!{_Reset_}")

    # 2. Load Facebook cookies
    cookies = load_cookies_from_input()
    if cookies:
        with open("cookie.txt", "w", encoding="utf-8") as f:
            f.write("|".join(cookies))
        print(f"{_Green_}Đã lưu {len(cookies)} cookie vào cookie.txt{_Reset_}")

    # 3. Get TTC Token
    ttc_token = get_ttc_token(ttc_cookies)
    if not ttc_token:
        print(f"{_Red_}Không lấy được token TTC.{_Reset_}")
        return
        
    # 4. Get TTC Account Info
    ttc_info = get_account_info(ttc_token)
    if ttc_info.get('status') == 'success':
        user_data = ttc_info.get('data', {})
        print(f"{_Green_}Tài khoản TTC: {user_data.get('user')} - Số xu: {user_data.get('sodu')}{_Reset_}")
    
    # 5. Load Facebook Accounts
    all_accounts = load_and_validate_cookies()
    if not all_accounts:
        print(f"{_Red_}Không tìm thấy cookie Facebook hợp lệ trong cookie.txt.{_Reset_}")
        return
    
    # 6. Select accounts to use
    accounts = select_accounts(all_accounts)
    print(f"{_Green_}Đã chọn {len(accounts)} tài khoản để chạy job.{_Reset_}")
    
    # 7. Configure Settings
    settings = setup_settings()
    
    # 8. Select Job Types
    print_section("Chọn loại Job muốn thực hiện")
    print("1. Reaction (Thường + VIP)")  
    print("2. Follow")
    print("3. Share")
    print("4. All (Tất cả các loại)")
    job_choice = input(f"{_Yellow_}Lựa chọn của bạn (mặc định: 4): {_Reset_}") or "4"
    
    selected_job_types = []
    if job_choice == "1": selected_job_types = ["reaction"]
    elif job_choice == "2": selected_job_types = ["follow"]
    elif job_choice == "3": selected_job_types = ["share"]
    else: selected_job_types = ["reaction", "follow", "share"]

    reaction_fetchers = [
        # ("Reaction (Thường)", get_reaction_jobs),
        ("Reaction (VIP)", get_vip_reaction_jobs),
        ("Reaction (VIP-RE)", get_vip_re_reaction_jobs)
    ]
    
    # --- Main Loop ---
    print_section("Bắt đầu thực hiện Job")
    total_jobs = 0
    account_index = 0
    jobs_this_account = {}  # Track jobs per account using dict
    attempted_jobs = set()
    
    try:
        while True:
            current_fb_account = accounts[account_index]
            current_uid = current_fb_account.uid
            
            # Reset job counter if limit reached
            if jobs_this_account.get(current_uid, 0) >= settings['JOBS_BEFORE_SWITCH']:
                print(f"\n{_Purple_}Đã hoàn thành {jobs_this_account[current_uid]} jobs, làm lại từ đầu...{_Reset_}")
                jobs_this_account[current_uid] = 0
                account_index = (account_index + 1) % len(accounts)
                current_fb_account = accounts[account_index]
                current_uid = current_fb_account.uid
                time.sleep(3)  # Short pause before continuing
            
            # Initialize or get current job count
            if current_uid not in jobs_this_account:
                jobs_this_account[current_uid] = 0
                
            interactor = FacebookInteractor(current_fb_account)
            print(f"\n{_Bold_}{_Blue_}Đang sử dụng FB: {current_fb_account.name} ({jobs_this_account[current_uid]}/{settings['JOBS_BEFORE_SWITCH']} jobs){_Reset_}")
            
            # Process reaction jobs
            if "reaction" in selected_job_types and jobs_this_account[current_uid] < settings['JOBS_BEFORE_SWITCH']:
                for name, fetcher in reaction_fetchers:
                    if jobs_this_account[current_uid] >= settings['JOBS_BEFORE_SWITCH']:
                        break
                        
                    print(f"Đang tìm job '{name}'...")
                    jobs = fetcher(ttc_cookies)
                    if jobs:
                        print(f" -> {_Green_}Tìm thấy {len(jobs)} job.{_Reset_}")
                        for job in jobs:
                            if jobs_this_account[current_uid] >= settings['JOBS_BEFORE_SWITCH']:
                                break
                                
                            job_dict = job.copy() if isinstance(job, dict) else {"idpost": job}
                            # Add fetcher type to job for proper endpoint selection
                            job_dict["type"] = "reaction"
                            if name == "Reaction (VIP-RE)":
                                job_dict["link"] = "camxucvipre"  # Mark as VIP-RE job
                            elif name == "Reaction (VIP)":
                                job_dict["link"] = "camxucvipcheo"  # Mark as VIP job
                                
                            job_id = f"reaction_{job_dict['idpost']}"
                            
                            if job_id in attempted_jobs:
                                continue
                                
                            attempted_jobs.add(job_id)
                            try:
                                result, delay = process_reaction_job(job_dict, interactor, ttc_cookies, settings)
                                if result and (result.get('status') == 'success' or 'xu' in str(result.get('mess', '')).lower()):
                                    total_jobs += 1
                                    jobs_this_account[current_uid] += 1
                                    time.sleep(delay)
                                else:
                                    time.sleep(2)
                            except Exception as e:
                                print(f"{_Red_}Lỗi xử lý job reaction: {str(e)}{_Reset_}")
                                time.sleep(2)
                                continue

            # Process follow jobs
            if "follow" in selected_job_types and jobs_this_account[current_uid] < settings['JOBS_BEFORE_SWITCH']:
                print("Đang tìm job 'Follow'...")
                jobs = get_follow_jobs(ttc_cookies)
                if jobs:
                    print(f" -> {_Green_}Tìm thấy {len(jobs)} job.{_Reset_}")
                    for job in jobs:
                        if jobs_this_account[current_uid] >= settings['JOBS_BEFORE_SWITCH']:
                            break
                            
                        job['type'] = 'follow'
                        job_id = f"follow_{job['idpost']}"
                        
                        if job_id in attempted_jobs:
                            continue
                            
                        attempted_jobs.add(job_id)
                        try:
                            result, delay = process_follow_job(job, interactor, ttc_cookies, settings)
                            if result and (result.get('status') == 'success' or 'xu' in str(result.get('mess', '')).lower()):
                                total_jobs += 1
                                jobs_this_account[current_uid] += 1
                                time.sleep(delay)
                            else:
                                time.sleep(2)
                        except Exception as e:
                            print(f"{_Red_}Lỗi xử lý job follow: {str(e)}{_Reset_}")
                            time.sleep(2)
                            continue

            # Process share jobs 
            if "share" in selected_job_types and jobs_this_account[current_uid] < settings['JOBS_BEFORE_SWITCH']:
                print("Đang tìm job 'Share'...")
                jobs = get_share_jobs(ttc_cookies)
                if jobs:
                    print(f" -> {_Green_}Tìm thấy {len(jobs)} job.{_Reset_}")
                    for job in jobs:
                        if jobs_this_account[current_uid] >= settings['JOBS_BEFORE_SWITCH']:
                            break
                            
                        job['type'] = 'share'
                        job_id = f"share_{job['idpost']}"
                        
                        if job_id in attempted_jobs:
                            continue
                            
                        attempted_jobs.add(job_id)
                        try:
                            result, delay = process_share_job(job, interactor, ttc_cookies, settings)
                            if result and (result.get('status') == 'success' or 'xu' in str(result.get('mess', '')).lower()):
                                total_jobs += 1
                                jobs_this_account[current_uid] += 1
                                time.sleep(delay)
                            else:
                                time.sleep(2)
                        except Exception as e:
                            print(f"{_Red_}Lỗi xử lý job share: {str(e)}{_Reset_}")
                            time.sleep(2)
                            continue

            # Clear attempted jobs periodically
            if len(attempted_jobs) > 1000:
                attempted_jobs.clear()

            # Only wait if no jobs found
            if total_jobs == 0:
                print(f"\n{_Yellow_}Không có job nào. Chờ 15 giây rồi thử lại...{_Reset_}")
                time.sleep(15)

    except KeyboardInterrupt:
        print(f"\n{_Yellow_}Đã dừng bởi người dùng. Tạm biệt!{_Reset_}")
    except Exception as e:
        print(f"\n{_BgRed_}{_Bold_}Một lỗi nghiêm trọng đã xảy ra: {e}{_Reset_}")

if __name__ == "__main__":
    main()