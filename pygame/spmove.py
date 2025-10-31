import cv2
import mediapipe as mp
import pygame
import math
import random
import numpy as np

# --- 初期設定 ---

# MediaPipe Handsモデルと描画ツールを準備
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
hands = mp_hands.Hands(
    max_num_hands=2, # 両手を検出
    min_detection_confidence=0.7,
    min_tracking_confidence=0.7
)

# Pygameの初期化
pygame.init()
pygame.font.init()

# --- 画面レイアウト定義 ---
SCREEN_WIDTH, SCREEN_HEIGHT = 1280, 720
LEFT_PANEL_WIDTH = int(SCREEN_WIDTH * 0.2) # 256
GAME_PANEL_WIDTH = SCREEN_WIDTH - LEFT_PANEL_WIDTH # 1024
GAME_HEIGHT = SCREEN_HEIGHT # 720

# 各パネルのRectを定義
SCORE_PANEL_RECT = pygame.Rect(0, 0, LEFT_PANEL_WIDTH, int(SCREEN_HEIGHT * 0.4))
LOG_PANEL_RECT = pygame.Rect(0, SCORE_PANEL_RECT.height, LEFT_PANEL_WIDTH, int(SCREEN_HEIGHT * 0.3))
CAM_PANEL_RECT = pygame.Rect(0, SCORE_PANEL_RECT.height + LOG_PANEL_RECT.height, LEFT_PANEL_WIDTH, int(SCREEN_HEIGHT * 0.3))
GAME_PANEL_RECT = pygame.Rect(LEFT_PANEL_WIDTH, 0, GAME_PANEL_WIDTH, GAME_HEIGHT)

# Pygameウィンドウの設定
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("MediaPipe Fighting Game")

# 色とフォントの定義
WHITE = (255, 255, 255)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLACK = (0, 0, 0)
GRAY = (50, 50, 50)
SKY_BLUE = (135, 206, 235)
BLUE = (0, 0, 255)
ORANGE = (255, 165, 0)
YELLOW = (255, 255, 0)
PURPLE = (128, 0, 128)

font_ui = pygame.font.Font(None, 36)
font_log = pygame.font.Font(None, 24)
font_title = pygame.font.Font(None, 40)
font_result = pygame.font.Font(None, 100)

# --- 画像読み込み (フォールバック付) ---

def load_image(path, size=None, fallback_color=ORANGE):
    """画像読み込み関数。失敗したら色付きのSurfaceを返す"""
    try:
        image = pygame.image.load(path).convert_alpha()
        if size:
            image = pygame.transform.scale(image, size)
        return image
    except FileNotFoundError:
        print(f"エラー: 画像 '{path}' が見つかりません。代替図形を使います。")
        if size:
            surface = pygame.Surface(size, pygame.SRCALPHA)
        else:
            # サイズ指定なしの場合、デフォルトサイズ
            surface = pygame.Surface((100, 100), pygame.SRCALPHA) 
        surface.fill(fallback_color)
        return surface

# --- 画像読み込み ---
# (画像読み込み部分は元のコードから変更ありません)

# プレイヤー画像
PLAYER_SIZE = (200, 400)
img_kihon = load_image("image/kihon.png", PLAYER_SIZE, BLUE)
img_punch_right = load_image("image/rightattack.png", PLAYER_SIZE, (0, 0, 200))
img_punch_left = load_image("image/leftattack.png", PLAYER_SIZE, (0, 0, 180))
img_kikouha = load_image("image/kikouha.png", PLAYER_SIZE, (0, 100, 200))
img_hado = load_image("image/hissatuhado.png", PLAYER_SIZE, (100, 100, 255))
img_guard = load_image("image/gard.png", (100, 400), (0, 200, 200)) # ガード用

# ダンサーアニメーション画像の読み込み
dancer_images = []
dancer_frame = 0
dancer_frame_time = 0
ANIMATION_SPEED_MS = 100
try:
    for i in range(1, 6):
        img_path = f"image/c-dancer-{i}.png"
        img = pygame.image.load(img_path).convert_alpha()
        img = pygame.transform.scale(img, (300, 300))
        dancer_images.append(img)
except FileNotFoundError as e:
    print(f"エラー: ダンサー画像が見つかりません。 {e}")

# 敵画像
ENEMY_SIZE = (200, 400)
img_enemy = load_image("image/damager.png", ENEMY_SIZE, RED)

# 弾 / エフェクト画像
img_ball = load_image("image/ball.png", (50, 50), RED)

# 気弾アニメーションリスト
img_kidan = [
    load_image("image/kidan3.png", (80, 80), YELLOW), # 手前から
    load_image("image/kidan2.png", (80, 80), YELLOW),
    load_image("image/kidan1.png", (80, 80), YELLOW), # 奥へ
]
# 波動アニメーションリスト
img_hado_bullets_raw = [
    load_image("image/hado4.png", (90, 150), PURPLE),
    load_image("image/hado2.png", (90, 150), PURPLE),
    load_image("image/hado1.png", (90, 150), PURPLE),
]


# ダメージエフェクトのサイズを拡大
EFFECT_SCALE = 1.5
img_dageki_dm = load_image("image/dagekidm.png", (int(100 * EFFECT_SCALE), int(100 * EFFECT_SCALE)), ORANGE)
img_kidan_dm = load_image("image/kidandm.png", (int(150 * EFFECT_SCALE), int(150 * EFFECT_SCALE)), YELLOW)
img_hado_dm = load_image("image/hadodm.png", (int(200 * EFFECT_SCALE), int(200 * EFFECT_SCALE)), PURPLE)

# 終了画面用
goal_background_image = None
try:
    img = pygame.image.load("image/goaliceclimb.png").convert()
    goal_background_image = pygame.transform.scale(img, (GAME_PANEL_WIDTH, GAME_HEIGHT))
except FileNotFoundError:
    print("エラー: image/goaliceclimb.png が見つかりません。")


# --- Webカメラの準備 ---
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("エラー: カメラを起動できません。")

# --- ★ 格闘ゲーム変数 ★ ---

# ステータス
player_hp = 10000
PLAYER_MAX_HP = 10000
player_energy = 100
PLAYER_MAX_ENERGY = 100
enemy_hp = 10000
ENEMY_MAX_HP = 10000
enemy_heal_count = 20

# 位置
player_rect = img_kihon.get_rect(center=(GAME_PANEL_WIDTH * 0.20, GAME_HEIGHT // 2))
enemy_rect = img_enemy.get_rect(center=(GAME_PANEL_WIDTH * 0.80, GAME_HEIGHT // 2))
guard_rect = img_guard.get_rect(center=(player_rect.centerx + 75, player_rect.centery))

# 状態管理
player_state = 'kihon' # kihon, punch_right, punch_left, kikouha, hado, guard
player_state_timer = 0
game_finished = False
game_won = False

# 弾 と エフェクト のリスト
player_bullets = [] # [Rect, 'type', speed]
enemy_bullets = [] # [Rect, vector_x, vector_y]
hit_effects = [] # [Image, Rect, timer]

# 敵の行動タイマー
enemy_heal_timer = 0
enemy_attack_timer = 0
enemy_next_attack_time = random.randint(5000, 8000)

# 防御タイマー
guard_start_time = 0
guard_duration_ms = 0
last_guard_bonus_time = 0

# ジェスチャー判定用 (Z座標ロジック含む)
prev_user_left_is_open = False
prev_user_right_is_open = False
prev_user_left_is_punching = False
prev_user_right_is_punching = False

# パンチ判定用のZ座標の閾値
PUNCH_Z_THRESHOLD = -0.1

# テキストログ
log_messages = []
MAX_LOG_LINES = 6

# --- 関数定義 ---

def add_log(message):
    log_messages.append(message)
    if len(log_messages) > MAX_LOG_LINES:
        log_messages.pop(0)

def format_time(ms):
    total_seconds = ms // 1000
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    milliseconds = (ms % 1000) // 10
    return f"{minutes:02}:{seconds:02}.{milliseconds:02}"

def is_hand_open(hand_landmarks):
    """手がパー(開いている)かどうかを判定する (Hands版)"""
    if not hand_landmarks:
        return False
    try:
        tip_ids = [mp_hands.HandLandmark.INDEX_FINGER_TIP, mp_hands.HandLandmark.MIDDLE_FINGER_TIP, mp_hands.HandLandmark.RING_FINGER_TIP, mp_hands.HandLandmark.PINKY_TIP]
        pip_ids = [mp_hands.HandLandmark.INDEX_FINGER_PIP, mp_hands.HandLandmark.MIDDLE_FINGER_PIP, mp_hands.HandLandmark.RING_FINGER_PIP, mp_hands.HandLandmark.PINKY_PIP]
        
        open_fingers = sum(1 for tip_id, pip_id in zip(tip_ids, pip_ids) if hand_landmarks.landmark[tip_id].y < hand_landmarks.landmark[pip_id].y)
        
        # 3本以上開いていれば「パー」と判定
        return open_fingers >= 3
    except:
        return False

def is_fingertips_touching(user_left_hand, user_right_hand):
    """両手の親指、人差し指、中指の先端が接触しているか判定する (ガード用)"""
    if not user_left_hand or not user_right_hand:
        return False
    
    try:
        left_thumb_tip = user_left_hand.landmark[mp_hands.HandLandmark.THUMB_TIP]
        left_index_tip = user_left_hand.landmark[mp_hands.HandLandmark.INDEX_FINGER_TIP]
        left_middle_tip = user_left_hand.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_TIP]
        
        right_thumb_tip = user_right_hand.landmark[mp_hands.HandLandmark.THUMB_TIP]
        right_index_tip = user_right_hand.landmark[mp_hands.HandLandmark.INDEX_FINGER_TIP]
        right_middle_tip = user_right_hand.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_TIP]
        
        TOUCH_THRESHOLD = 0.07 

        dist_thumb = math.hypot(left_thumb_tip.x - right_thumb_tip.x, left_thumb_tip.y - right_thumb_tip.y)
        dist_index = math.hypot(left_index_tip.x - right_index_tip.x, left_index_tip.y - right_index_tip.y)
        dist_middle = math.hypot(left_middle_tip.x - right_middle_tip.x, left_middle_tip.y - right_middle_tip.y)
        
        if (dist_thumb < TOUCH_THRESHOLD) and \
           (dist_index < TOUCH_THRESHOLD) and \
           (dist_middle < TOUCH_THRESHOLD):
            return True
        
        return False
    except:
        return False


def is_punching(hand_landmarks):
    """手がグーの状態で、Z軸方向に突き出されているか判定する"""
    if not hand_landmarks:
        return False
    
    # ★重要★ まず、手がグーかどうかを判定 (パーではない)
    # これにより、パーで突き出す動作をパンチと誤認するのを防ぐ
    if is_hand_open(hand_landmarks):
        return False
        
    try:
        wrist = hand_landmarks.landmark[mp_hands.HandLandmark.WRIST]
        tip_index = hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_TIP]
        
        # 手首に対する指先の相対Z座標
        relative_z = tip_index.z - wrist.z
        
        # 指先が手首よりも一定以上奥にあれば(Zが小さければ)「パンチ」と判定
        if relative_z < PUNCH_Z_THRESHOLD:
            return True
        return False
    except:
        return False


def draw_bar(surface, rect, value, max_value, color, bg_color=GRAY):
    """HPバーやエナジーバーを描画する"""
    pygame.draw.rect(surface, bg_color, rect)
    ratio = value / max_value
    bar_width = int(rect.width * ratio)
    pygame.draw.rect(surface, color, (rect.x, rect.y, bar_width, rect.height))
    pygame.draw.rect(surface, WHITE, rect, 2)


# --- メインループ ---
running = True
clock = pygame.time.Clock()
add_log("Game Start!")
camera_surface_scaled = None # カメラ映像保持用

while running:

    delta_time_ms = clock.get_time()
    current_time_ms = pygame.time.get_ticks()

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                running = False

    screen.fill(GRAY)

    if game_finished:
        # --- GAME FINISHED ---
        
        game_surface = screen.subsurface(GAME_PANEL_RECT)
        if goal_background_image:
            game_surface.blit(goal_background_image, (0, 0))
        else:
            game_surface.fill(SKY_BLUE)

        if game_won:
            result_text_str = "Win!!"
            result_color = ORANGE
        else:
            result_text_str = "You Lose..."
            result_color = RED
            
        result_text = font_result.render(result_text_str, True, result_color)
        game_surface.blit(result_text, (
            game_surface.get_width() // 2 - result_text.get_width() // 2,
            game_surface.get_height() // 3 - result_text.get_height() // 2
        ))
        
        if dancer_images:
            dancer_frame_time += delta_time_ms
            if dancer_frame_time > ANIMATION_SPEED_MS:
                dancer_frame = (dancer_frame + 1) % len(dancer_images)
                dancer_frame_time = 0

            current_dancer_image = dancer_images[dancer_frame]
            img_rect = current_dancer_image.get_rect(center=(game_surface.get_width() // 2, game_surface.get_height() // 2 + 100))
            game_surface.blit(current_dancer_image, img_rect)

        if cap.isOpened():
            cap.release()

    elif not game_finished:
        # --- GAME RUNNING ---

        camera_surface_scaled = None 
        results = None 

        if not cap.isOpened():
            if "Camera feed lost." not in log_messages:
                add_log("Camera feed lost.")
        else:
            success, image_cam = cap.read()
            if not success:
                if "Camera frame read error." not in log_messages:
                    add_log("Camera frame read error.")
            else:
                # 2. Hands 検出
                image_rgb = cv2.cvtColor(cv2.flip(image_cam, 1), cv2.COLOR_BGR2RGB)
                image_rgb.flags.writeable = False
                results = hands.process(image_rgb)

                # 3. カメラ映像の準備 (左下パネル用)
                image_bgr = cv2.cvtColor(image_rgb, cv2.COLOR_BGR2RGB)
                
                if results.multi_hand_landmarks:
                    for hand_landmarks in results.multi_hand_landmarks:
                        mp_drawing.draw_landmarks(
                            image_bgr,
                            hand_landmarks,
                            mp_hands.HAND_CONNECTIONS, 
                            mp_drawing.DrawingSpec(color=GREEN, thickness=2, circle_radius=2),
                            mp_drawing.DrawingSpec(color=WHITE, thickness=2, circle_radius=2))

                image_rgb_cam = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
                image_pygame = pygame.image.frombuffer(image_rgb_cam.tobytes(), image_rgb_cam.shape[1::-1], "RGB")
                camera_surface_scaled = pygame.transform.scale(image_pygame, (CAM_PANEL_RECT.width, CAM_PANEL_RECT.height))


        # 4. 格闘ゲーム ジェスチャーロジック
        
        is_user_left_open = False
        is_user_right_open = False
        is_user_left_punching = False
        is_user_right_punching = False
        
        user_left_hand_landmarks = None
        user_right_hand_landmarks = None

        if results and results.multi_hand_landmarks:
            for hand_landmarks, handedness in zip(results.multi_hand_landmarks, results.multi_handedness):
                hand_label = handedness.classification[0].label
                
                # MediaPipeの 'Left' はカメラから見て左 = プレイヤーの「右手」
                if hand_label == "Left": 
                    is_user_right_open = is_hand_open(hand_landmarks)
                    is_user_right_punching = is_punching(hand_landmarks)
                    user_right_hand_landmarks = hand_landmarks
                # MediaPipeの 'Right' はカメラから見て右 = プレイヤーの「左手」
                elif hand_label == "Right": 
                    is_user_left_open = is_hand_open(hand_landmarks)
                    is_user_left_punching = is_punching(hand_landmarks)
                    user_left_hand_landmarks = hand_landmarks


        # プレイヤー状態タイマー更新
        if player_state_timer > 0:
            player_state_timer -= delta_time_ms
        else:
            player_state = 'kihon'
            guard_duration_ms = 0


        # ジェスチャー判定
        
        # (1) 状態変化を検出
        # ★★★ 修正: グー -> パー (気弾/波動用) ★★★
        user_left_just_opened = (not prev_user_left_is_open) and is_user_left_open
        user_right_just_opened = (not prev_user_right_is_open) and is_user_right_open
        
        # 突き -> 戻し (パンチ用)
        user_left_just_punched = (not prev_user_left_is_punching) and is_user_left_punching
        user_right_just_punched = (not prev_user_right_is_punching) and is_user_right_punching


        # (3) ★★★ 修正: 攻撃判定 (kihon状態の時のみ) ★★★
        if player_state == 'kihon':
            
            # ★★★ 修正: 優先1: 波動 (両手が グー -> パー) ★★★
            if (user_left_just_opened and user_right_just_opened) and \
               player_energy >= 5:
                
                player_state = 'hado'
                player_state_timer = 1500 # 1.5秒硬直
                player_energy -= 5
                add_log("HADO! (E-5)")
                hado_width = sum(img.get_width() for img in img_hado_bullets_raw)
                hado_height = img_hado_bullets_raw[0].get_height()
                player_bullets.append([pygame.Rect(player_rect.right, player_rect.centery - hado_height // 2 + 30, hado_width, hado_height), 'hado', 7]) # 弾速 7 

            # 優先2: 打撃 (両手グー ＆ 片手突き) (変更なし)
            elif (not is_user_left_open and not is_user_right_open) and \
                 (user_left_just_punched != user_right_just_punched) and \
                 player_energy >= 1:

                enemy_hp -= 100
                hit_effects.append([img_dageki_dm, img_dageki_dm.get_rect(center=enemy_rect.center), 200]) # 0.2秒
                
                if user_left_just_punched: # ユーザーの左手
                    player_state = 'punch_left'
                    add_log("LEFT PUNCH! (E-1)")
                else: # user_right_just_punched # ユーザーの右手
                    player_state = 'punch_right'
                    add_log("RIGHT PUNCH! (E-1)")
                    
                player_state_timer = 100 # 0.1秒硬直
                player_energy -= 1

            # ★★★ 修正: 優先3: 気弾 (片手が グー -> パー) ★★★
            elif (user_left_just_opened != user_right_just_opened) and \
                 player_energy >= 2:
                
                player_state = 'kikouha'
                player_state_timer = 1000 # 1秒硬直
                player_energy -= 2
                add_log("KIKOUHA! (E-2)")
                kidan_width = sum(img.get_width() for img in img_kidan)
                kidan_height = img_kidan[0].get_height()
                player_bullets.append([pygame.Rect(player_rect.right, player_rect.centery - kidan_height // 2, kidan_width, kidan_height), 'kidan', 5]) # 弾速 5

            # 優先4: ガード (指先合わせ) (変更なし)
            elif is_fingertips_touching(user_left_hand_landmarks, user_right_hand_landmarks):
                player_state = 'guard'
                guard_start_time = current_time_ms
                guard_duration_ms = 0

        # (5) 防御継続判定
        if player_state == 'guard':
            if is_fingertips_touching(user_left_hand_landmarks, user_right_hand_landmarks):
                guard_duration_ms = current_time_ms - guard_start_time
                
            else:
                player_state = 'kihon' # 防御解除
                guard_duration_ms = 0
                last_guard_bonus_time = 0


        # 判定用に現在の状態を保存
        prev_user_left_is_open = is_user_left_open
        prev_user_right_is_open = is_user_right_open
        prev_user_left_is_punching = is_user_left_punching
        prev_user_right_is_punching = is_user_right_punching


        # 5. ゲームロジック更新
        
        # (1) 敵の回復
        enemy_heal_timer += delta_time_ms
        if enemy_heal_timer >= 1000: # 1秒ごと
            enemy_heal_timer = 0
            if enemy_hp < ENEMY_MAX_HP and enemy_heal_count > 0:
                heal_amount = int(enemy_hp * 0.03)
                enemy_hp = min(ENEMY_MAX_HP, enemy_hp + heal_amount)
                enemy_heal_count -= 1

        # (2) 敵の攻撃
        enemy_attack_timer += delta_time_ms
        if enemy_attack_timer >= enemy_next_attack_time:
            enemy_attack_timer = 0
            enemy_next_attack_time = random.randint(5000, 10000)
            num_balls = random.randint(1, 5)
            add_log(f"Enemy attacks! ({num_balls} balls)")
            for _ in range(num_balls):
                ball_rect = img_ball.get_rect(center=enemy_rect.center)
                dx = player_rect.centerx - enemy_rect.centerx
                dy = player_rect.centery - enemy_rect.centery
                dist = math.hypot(dx, dy)
                if dist == 0: dist = 1
                vx = (dx / dist) * 5 #10→5
                vy = (dy / dist) * 5 #10→5
                enemy_bullets.append([ball_rect, vx, vy])

        # (3) プレイヤーの弾の移動と当たり判定
        for bullet in player_bullets[:]: 
            bullet[0].x += bullet[2] # speed

            # 敵との当たり判定
            if bullet[0].colliderect(enemy_rect):
                if bullet[1] == 'kidan':
                    enemy_hp -= 400 
                    hit_effects.append([img_kidan_dm, img_kidan_dm.get_rect(center=enemy_rect.center), 200])
                elif bullet[1] == 'hado':
                    enemy_hp -= 1000 
                    hit_effects.append([img_hado_dm, img_hado_dm.get_rect(center=enemy_rect.center), 200])
                player_bullets.remove(bullet)
                continue
            
            # 画面外
            if bullet[0].left > GAME_PANEL_WIDTH:
                player_bullets.remove(bullet)
                continue
            
            # 敵の弾との相殺 (気弾のみ)
            if bullet[1] == 'kidan':
                collided_with_enemy_ball = False
                for enemy_ball in enemy_bullets[:]:
                    if bullet[0].colliderect(enemy_ball[0]):
                        collision_point = bullet[0].center
                        hit_effects.append([img_kidan_dm, img_kidan_dm.get_rect(center=collision_point), 200])
                        player_bullets.remove(bullet)
                        enemy_bullets.remove(enemy_ball)
                        add_log("Offset!")
                        collided_with_enemy_ball = True
                        break 
                
                if collided_with_enemy_ball:
                    continue
            # 敵の弾を貫通 (波動のみ)
            elif bullet[1] == 'hado':
                for enemy_ball in enemy_bullets[:]:
                    if bullet[0].colliderect(enemy_ball[0]):
                        collision_point = enemy_ball[0].center # 敵の弾の位置にエフェクト
                        hit_effects.append([img_hado_dm, img_hado_dm.get_rect(center=collision_point), 200])
                        enemy_bullets.remove(enemy_ball) # 敵の弾だけ消える
                        add_log("Hado breaks ball!")
                        # 波動(bullet)は削除しない
                        # breakもしない (波動は複数の敵の弾を貫通できるため)


        # (4) 敵の弾の移動と当たり判定
        for ball in enemy_bullets[:]:
            ball[0].x += ball[1] # vx
            ball[0].y += ball[2] # vy
            
            if player_state == 'guard' and ball[0].colliderect(guard_rect):
                enemy_bullets.remove(ball)
                
                # ★★★ 修正: ガード成功ボーナス ★★★
                add_log("Guarded! HP+100, E+1")
                player_hp = min(PLAYER_MAX_HP, player_hp + 100)
                player_energy = min(PLAYER_MAX_ENERGY, player_energy + 1)
                
                continue
            
            if ball[0].colliderect(player_rect):
                player_hp -= 200
                enemy_bullets.remove(ball)
                add_log("Hit! (HP-200)")
                continue

            if ball[0].right < 0 or ball[0].top > GAME_HEIGHT or ball[0].bottom < 0:
                enemy_bullets.remove(ball)

        # (5) ヒットエフェクトのタイマー更新
        for effect in hit_effects[:]:
            effect[2] -= delta_time_ms
            if effect[2] <= 0:
                hit_effects.remove(effect)

        # (6) HP/エナジーのクランプ
        player_hp = max(0, player_hp)
        player_energy = max(0, min(PLAYER_MAX_ENERGY, player_energy))
        enemy_hp = max(0, enemy_hp)

        # (7) ゲーム終了判定
        if player_hp <= 0:
            game_finished = True
            game_won = False
            add_log("You Lose...")
        elif enemy_hp <= 0:
            game_finished = True
            game_won = True
            add_log("Win!!")


        # 6. Pygame ゲーム画面描画
        
        game_surface = screen.subsurface(GAME_PANEL_RECT)
        game_surface.fill(SKY_BLUE) 

        # プレイヤー描画
        if player_state == 'kihon':
            game_surface.blit(img_kihon, player_rect)
        elif player_state == 'punch_right':
            game_surface.blit(img_punch_right, player_rect)
        elif player_state == 'punch_left':
            game_surface.blit(img_punch_left, player_rect)
        elif player_state == 'kikouha':
            game_surface.blit(img_kikouha, player_rect)
        elif player_state == 'hado':
            game_surface.blit(img_hado, player_rect)
        elif player_state == 'guard':
            game_surface.blit(img_kihon, player_rect) 
            game_surface.blit(img_guard, guard_rect) 

        # 敵描画
        game_surface.blit(img_enemy, enemy_rect)
        
        # プレイヤーの弾 描画 (連結描画)
        for bullet in player_bullets:
            draw_x = bullet[0].left
            if bullet[1] == 'kidan':
                for img in img_kidan:
                    game_surface.blit(img, (draw_x, bullet[0].top))
                    draw_x += img.get_width()
            elif bullet[1] == 'hado':
                #for img in img_hado_animation_list:
                for img in img_hado_bullets_raw:
                    game_surface.blit(img, (draw_x, bullet[0].top))
                    draw_x += img.get_width()

        # 敵の弾 描画
        for ball in enemy_bullets:
            game_surface.blit(img_ball, ball[0])

        # エフェクト 描画
        for effect in hit_effects:
            game_surface.blit(effect[0], effect[1]) # img, rect

        # HP/エナジーバー 描画
        draw_bar(game_surface, pygame.Rect(player_rect.left, player_rect.top - 30, player_rect.width, 20), player_hp, PLAYER_MAX_HP, GREEN)
        draw_bar(game_surface, pygame.Rect(player_rect.left, player_rect.top - 55, player_rect.width, 20), player_energy, PLAYER_MAX_ENERGY, BLUE)
        draw_bar(game_surface, pygame.Rect(enemy_rect.left, enemy_rect.top - 30, enemy_rect.width, 20), enemy_hp, ENEMY_MAX_HP, RED)


    # --- UIパネルの描画 (全状態共通) ---

    # --- スコアパネル (左上) ---
    score_surface = screen.subsurface(SCORE_PANEL_RECT)
    score_surface.fill(BLACK)
    title_text = font_title.render("STATUS", True, WHITE)
    score_surface.blit(title_text, (10, 10))
    
    player_hp_text = font_ui.render(f"Player HP: {player_hp}", True, GREEN)
    score_surface.blit(player_hp_text, (15, 60))

    player_en_text = font_ui.render(f"Energy: {player_energy}", True, ORANGE)
    score_surface.blit(player_en_text, (15, 100))

    enemy_hp_text = font_ui.render(f"Enemy HP: {enemy_hp}", True, RED)
    score_surface.blit(enemy_hp_text, (15, 140))
    
    enemy_heal_text = font_ui.render(f"Heal: {enemy_heal_count}", True, WHITE)
    score_surface.blit(enemy_heal_text, (15, 180))
    
    r_text1 = font_log.render("Please reload,", True, GREEN)
    r_text2 = font_log.render("if you want to retry.", True, GREEN)
    score_surface.blit(r_text1, (15, 230))
    score_surface.blit(r_text2, (15, 260))


    # --- ログパネル (左中) ---
    log_surface = screen.subsurface(LOG_PANEL_RECT)
    log_surface.fill(BLACK)
    log_title = font_title.render("LOG", True, WHITE)
    log_surface.blit(log_title, (10, 10))
    y_pos = 50
    for message in log_messages:
        log_text = font_log.render(message, True, GREEN)
        log_surface.blit(log_text, (15, y_pos))
        y_pos += 25

    # --- カメラパネル (左下) ---
    cam_title = font_title.render("CAMERA", True, WHITE)
    cam_surface = screen.subsurface(CAM_PANEL_RECT)
    pygame.draw.rect(cam_surface, BLACK, (0, 0, CAM_PANEL_RECT.width, CAM_PANEL_RECT.height))
    cam_surface.blit(cam_title, (10, 10)) 

    if not game_finished:
        if cap.isOpened() and camera_surface_scaled:
            cam_surface.blit(camera_surface_scaled, (0, 30))
        elif not cap.isOpened():
            cam_error_text = font_log.render("Camera not found.", True, RED)
            cam_surface.blit(cam_error_text, (10, 50))

    # 画面更新 (全状態共通)
    pygame.display.flip()
    clock.tick(30)

# --- 終了処理 ---
if cap.isOpened():
    cap.release()
cv2.destroyAllWindows()
pygame.quit()
