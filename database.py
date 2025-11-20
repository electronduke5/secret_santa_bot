import json
import os
from typing import Dict, List, Optional
import random
import string

DB_FILE = "data.json"


def init_db():
    """Инициализация базы данных если её не существует"""
    if not os.path.exists(DB_FILE):
        data = {"groups": {}}
        save_db(data)


def load_db() -> Dict:
    """Загрузка данных из JSON файла"""
    init_db()
    with open(DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_db(data: Dict):
    """Сохранение данных в JSON файл"""
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def generate_invite_code() -> str:
    """Генерация уникального кода приглашения"""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))


def create_group(admin_id: int, admin_name: str, admin_username: Optional[str], group_name: str) -> str:
    """Создание новой группы"""
    data = load_db()

    invite_code = generate_invite_code()
    # Проверяем уникальность кода
    while invite_code in data["groups"]:
        invite_code = generate_invite_code()

    data["groups"][invite_code] = {
        "name": group_name,
        "admin_id": admin_id,
        "invite_code": invite_code,
        "participants": {
            str(admin_id): {
                "first_name": admin_name,
                "username": admin_username,
                "wishlist": ""
            }
        },
        "assignments": {},
        "is_distributed": False
    }

    save_db(data)
    return invite_code


def get_group(invite_code: str) -> Optional[Dict]:
    """Получение информации о группе"""
    data = load_db()
    return data["groups"].get(invite_code)


def join_group(invite_code: str, user_id: int, user_name: str, username: Optional[str]) -> bool:
    """Присоединение пользователя к группе"""
    data = load_db()

    if invite_code not in data["groups"]:
        return False

    group = data["groups"][invite_code]

    # Проверяем, что распределение ещё не началось
    if group["is_distributed"]:
        return False

    # Добавляем пользователя
    group["participants"][str(user_id)] = {
        "first_name": user_name,
        "username": username,
        "wishlist": ""
    }

    save_db(data)
    return True


def get_user_groups(user_id: int) -> List[Dict]:
    """Получение списка групп пользователя"""
    data = load_db()
    user_groups = []

    for invite_code, group in data["groups"].items():
        if str(user_id) in group["participants"]:
            user_groups.append({
                "name": group["name"],
                "invite_code": invite_code,
                "is_admin": group["admin_id"] == user_id,
                "participants_count": len(group["participants"]),
                "is_distributed": group["is_distributed"]
            })

    return user_groups


def set_wishlist(user_id: int, invite_code: str, wishlist: str) -> bool:
    """Установка списка пожеланий пользователя"""
    data = load_db()

    if invite_code not in data["groups"]:
        return False

    group = data["groups"][invite_code]

    if str(user_id) not in group["participants"]:
        return False

    group["participants"][str(user_id)]["wishlist"] = wishlist
    save_db(data)
    return True


def get_wishlist(user_id: int, invite_code: str) -> Optional[str]:
    """Получение списка пожеланий пользователя"""
    data = load_db()

    if invite_code not in data["groups"]:
        return None

    group = data["groups"][invite_code]

    if str(user_id) not in group["participants"]:
        return None

    return group["participants"][str(user_id)].get("wishlist", "")


def distribute_santa(invite_code: str) -> bool:
    """Случайное распределение участников Тайного Санты"""
    data = load_db()

    if invite_code not in data["groups"]:
        return False

    group = data["groups"][invite_code]

    # Проверяем количество участников (минимум 3)
    if len(group["participants"]) < 3:
        return False

    # Получаем список ID участников
    participants = list(group["participants"].keys())

    # Перемешиваем список
    shuffled = participants.copy()
    random.shuffle(shuffled)

    # Создаём распределение по кругу
    assignments = {}
    for i in range(len(shuffled)):
        giver = shuffled[i]
        receiver = shuffled[(i + 1) % len(shuffled)]
        assignments[giver] = receiver

    group["assignments"] = assignments
    group["is_distributed"] = True

    save_db(data)
    return True


def get_recipient(user_id: int, invite_code: str) -> Optional[Dict]:
    """Получение информации о получателе подарка"""
    data = load_db()

    if invite_code not in data["groups"]:
        return None

    group = data["groups"][invite_code]

    if not group["is_distributed"]:
        return None

    if str(user_id) not in group["assignments"]:
        return None

    recipient_id = group["assignments"][str(user_id)]
    recipient_info = group["participants"][recipient_id]

    return {
        "first_name": recipient_info["first_name"],
        "username": recipient_info["username"],
        "wishlist": recipient_info.get("wishlist", "")
    }


def cancel_distribution(invite_code: str) -> bool:
    """Отмена распределения"""
    data = load_db()

    if invite_code not in data["groups"]:
        return False

    group = data["groups"][invite_code]
    group["assignments"] = {}
    group["is_distributed"] = False

    save_db(data)
    return True
