import requests
import os

def load_credentials(filename="login_tickets_info.txt"):
    """로그인 정보를 파일에서 불러오는 함수"""
    credentials = {}
    try:
        with open(filename, "r") as file:
            for line in file:
                parts = line.strip().split("=")
                if len(parts) == 2:
                    key, value = parts
                    credentials[key.strip()] = value.strip()
    except FileNotFoundError:
        print("로그인 정보 파일을 찾을 수 없습니다. 파일 위치를 확인하세요.")
        exit(1)

    if "SWARM_URL" not in credentials or "USERNAME" not in credentials or "PASSWORD" not in credentials:
        print("로그인 정보 파일이 올바르지 않습니다. 필요한 값이 빠졌을 수 있습니다.")
        exit(1)

    return credentials

# 로그인 정보 가져오기
credentials = load_credentials()
SWARM_URL = credentials["SWARM_URL"]
USERNAME = credentials["USERNAME"]
PASSWORD = credentials["PASSWORD"]

# 특정 기간 동안의 변경 목록 가져오기
def get_changes(start_date, end_date, max_results=100):
    """주어진 기간 동안의 변경 목록을 Swarm API에서 조회"""
    url = f"{SWARM_URL}/api/v9/changes?max={max_results}&after={start_date}&before={end_date}"

    try:
        response = requests.get(url, auth=(USERNAME, PASSWORD))
        response.raise_for_status()  # 오류 발생 시 예외 발생
        return response.json().get("changes", [])
    except requests.exceptions.RequestException as e:
        print(f"변경 목록을 가져오는 중 오류가 발생했습니다: {e}")
        return []

# 특정 changelist의 diff 가져오기
def get_diff(changelist_id):
    """특정 changelist의 diff 데이터를 Swarm API에서 조회"""
    url = f"{SWARM_URL}/api/v9/changes/{changelist_id}/diffs"

    try:
        response = requests.get(url, auth=(USERNAME, PASSWORD))
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Changelist {changelist_id}의 diff를 가져오는 중 오류 발생: {e}")
        return None

if __name__ == "__main__":
    # 조회할 기간 설정 (YYYY-MM-DDTHH:MM:SS 형식)
    start_date = "2024-02-01T00:00:00"
    end_date = "2024-02-28T23:59:59"

    print(f"{start_date} ~ {end_date} 기간 동안의 변경 목록을 조회합니다.")
    changes = get_changes(start_date, end_date)

    if not changes:
        print("변경 목록이 없습니다. 기간 설정을 확인하세요.")
        exit(0)

    print(f"{len(changes)}개의 변경 목록을 찾았습니다.")

    # 모든 changelist의 diff 조회
    for change in changes:
        changelist_id = change["id"]
        print(f"Changelist {changelist_id}의 diff 정보를 가져오는 중...")
        diff_data = get_diff(changelist_id)

        if diff_data:
            print(f"Changelist {changelist_id}의 변경 내용:")
            print(diff_data)
        else:
            print(f"Changelist {changelist_id}의 diff 데이터를 가져올 수 없습니다.")
