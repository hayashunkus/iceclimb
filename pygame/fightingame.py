#これは腕も検知する　あまりうまくいかない
import cv2
import mediapipe as mp
import pygame
import math
import random
import numpy as np

# --- 初期設定 ---

# MediaPipe Holisticモデルと描画ツールを準備
mp_holistic = mp.solutions.holistic
mp_drawing = mp.solutions.drawing_utils
holistic = mp_holistic.Holistic(
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

# --- ★ 画像読み込み (フォールバック付) ★ ---

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
img_kidan = [
    load_image("image/kidan1.png", (80, 80), YELLOW),
    load_image("image/kidan2.png", (80, 80), YELLOW),
    load_image("image/kidan3.png", (80, 80), YELLOW),
]
img_hado_bullets = [
    load_image("image/hado1.png", (120, 120), PURPLE),
    load_image("image/hado2.png", (120, 120), PURPLE),
    load_image("image/hado3.png", (120, 120), PURPLE),
    load_image("image/hado4.png", (120, 120), PURPLE),
]
# ★★★ 修正: 波動アニメーションリストを定義 ★★★
img_hado_animation_list = [
    img_hado_bullets[0], # hado1
    img_hado_bullets[1], # hado2
    img_hado_bullets[2], # hado3
    img_hado_bullets[2], # hado3
    img_hado_bullets[2], # hado3
    img_hado_bullets[3]  # hado4
]

img_dageki_dm = load_image("image/dagekidm.png", (100, 100), ORANGE)
img_kidan_dm = load_image("image/kidandm.png", (150, 150), YELLOW)
img_hado_dm = load_image("image/hadodm.png", (200, 200), PURPLE)

# 終了画面用 (ボルダリングのを流用)
goal_background_image = None
try:
    # この画像も image/ フォルダにあると想定して修正
    img = pygame.image.load("image/goaliceclimb.png").convert()
    goal_background_image = pygame.transform.scale(img, (GAME_PANEL_WIDTH, GAME_HEIGHT))
except FileNotFoundError:
    print("エラー: image/goaliceclimb.png が見つかりません。")

# --- ★★★ 修正箇所ここまで ★★★ ---


# --- Webカメラの準備 ---
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("エラー: カメラを起動できません。")

# --- ★ 格闘ゲーム変数 ★ ---

# ステータス (★ ユーザーのコードスニペットに基づき変更)
player_hp = 10000
PLAYER_MAX_HP = 10000
player_energy = 100
PLAYER_MAX_ENERGY = 100
enemy_hp = 5000
ENEMY_MAX_HP = 5000
enemy_heal_count = 10

# 位置
player_rect = img_kihon.get_rect(center=(GAME_PANEL_WIDTH * 0.25, GAME_HEIGHT // 2))
enemy_rect = img_enemy.get_rect(center=(GAME_PANEL_WIDTH * 0.75, GAME_HEIGHT // 2))
# ガードの位置 (プレイヤーの少し右)
guard_rect = img_guard.get_rect(center=(player_rect.centerx + 80, player_rect.centery))

# 状態管理
player_state = 'kihon' # kihon, punch_right, punch_left, kikouha, hado, guard
player_state_timer = 0 # 状態異常の残り時間 (ms)
game_finished = False
game_won = False

# 弾 と エフェクト のリスト
player_bullets = [] # [Rect, 'type', speed, animation_frame]
enemy_bullets = [] # [Rect, vector_x, vector_y]
hit_effects = [] # [Image, Rect, timer]

# 敵の行動タイマー
enemy_heal_timer = 0 # 1000ms になったら回復
enemy_attack_timer = 0
enemy_next_attack_time = random.randint(5000, 8000) # 次の攻撃までの時間 (ms)

# 防御タイマー
guard_start_time = 0
guard_duration_ms = 0

# ジェスチャー判定用
prev_left_elbow_angle = 180
prev_right_elbow_angle = 180

# ★★★ 修正: 角度のロジックを修正 ★★★
# 腕の角度の閾値 (度)
ELBOW_ANGLE_STRAIGHT = 160 # これより大きいと「伸びている」 (180に近い)
ELBOW_ANGLE_BENT = 100     # これより小さいと「曲がっている」 (90に近い)
GUARD_ANGLE = 90         # 防御判定 (これより小さいと曲がっている)

# テキストログ
log_messages = []
MAX_LOG_LINES = 6

# --- ★ 関数定義 ★ ---

def add_log(message):
    log_messages.append(message)
    if len(log_messages) > MAX_LOG_LINES:
        log_messages.pop(0)

def format_time(ms):
    # (ボルダリングから流用)
    total_seconds = ms // 1000
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    milliseconds = (ms % 1000) // 10
    return f"{minutes:02}:{seconds:02}.{milliseconds:02}"

def is_hand_open(hand_landmarks):
    """手がパー(開いている)かどうかを判定する (Holistic版)"""
    if not hand_landmarks:
        return False
    try:
        tip_ids = [mp_holistic.HandLandmark.INDEX_FINGER_TIP, mp_holistic.HandLandmark.MIDDLE_FINGER_TIP, mp_holistic.HandLandmark.RING_FINGER_TIP, mp_holistic.HandLandmark.PINKY_TIP]
        pip_ids = [mp_holistic.HandLandmark.INDEX_FINGER_PIP, mp_holistic.HandLandmark.MIDDLE_FINGER_PIP, mp_holistic.HandLandmark.RING_FINGER_PIP, mp_holistic.HandLandmark.PINKY_PIP]
        open_fingers = sum(1 for tip_id, pip_id in zip(tip_ids, pip_ids) if hand_landmarks.landmark[tip_id].y < hand_landmarks.landmark[pip_id].y)
        return open_fingers >= 3
    except:
        return False

def calculate_angle(a, b, c):
    """3つのランドマーク(a, b, c)から、b地点の角度を計算する"""
    try:
        # np.arrayに変換
        a = np.array([a.x, a.y])
        b = np.array([b.x, b.y])
        c = np.array([c.x, c.y])
        
        # ベクトル計算
        ba = a - b
        bc = c - b
        
        # 角度計算 (ラジアン)
        cosine_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc))
        angle = np.arccos(np.clip(cosine_angle, -1.0, 1.0)) # 念のためクリップ
        
        # 度数法に変換
        return np.degrees(angle)
    except:
        return 180 # エラー時は「伸びている」として処理 (安全のため)

def draw_bar(surface, rect, value, max_value, color, bg_color=GRAY):
    """HPバーやエナジーバーを描画する"""
    # 背景
    pygame.draw.rect(surface, bg_color, rect)
    # 値
    ratio = value / max_value
    bar_width = int(rect.width * ratio)
    pygame.draw.rect(surface, color, (rect.x, rect.y, bar_width, rect.height))
    # 枠
    pygame.draw.rect(surface, WHITE, rect, 2)


# --- メインループ ---
running = True
clock = pygame.time.Clock()
add_log("Game Start!")
camera_surface_scaled = None # カメラ映像保持用

while running:

    delta_time_ms = clock.get_time()

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                running = False

    screen.fill(GRAY)

    if game_finished:
        # --- ★★★ GAME FINISHED ★★★ ---
        
        game_surface = screen.subsurface(GAME_PANEL_RECT)
        if goal_background_image:
            game_surface.blit(goal_background_image, (0, 0))
        else:
            game_surface.fill(SKY_BLUE)

        # 結果テキスト (★ ユーザーのコードスニペットに基づき変更)
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
        
        # (★ ユーザーのコードスニペットに基づき追加)
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
        # --- ★★★ GAME RUNNING ★★★ ---

        # ★★★ 修正: カメラ関連の変数を毎フレームリセット ★★★
        camera_surface_scaled = None 
        results = None 

        # ★★★ 修正: カメラの起動チェックをループ内に移動 ★★★
        if not cap.isOpened():
            # カメラが見つからない場合、ログに追加（ループは継続）
            if "Camera feed lost." not in log_messages:
                 add_log("Camera feed lost.")
        else:
            # カメラが起動している場合、フレームを読み込む
            success, image_cam = cap.read()
            if not success:
                if "Camera frame read error." not in log_messages:
                    add_log("Camera frame read error.")
            else:
                # 2. Holistic 検出 (正常読み込み時のみ)
                # ★★★ 修正: COLOR_BGR_RGB -> COLOR_BGR2RGB ★★★
                image_rgb = cv2.cvtColor(cv2.flip(image_cam, 1), cv2.COLOR_BGR2RGB)
                image_rgb.flags.writeable = False
                results = holistic.process(image_rgb) # ★ results に結果を格納

                # 3. カメラ映像の準備 (左下パネル用)
                image_bgr = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
                mp_drawing.draw_landmarks(
                    image_bgr, results.pose_landmarks, mp_holistic.POSE_CONNECTIONS,
                    landmark_drawing_spec=mp_drawing.DrawingSpec(color=GREEN, thickness=2, circle_radius=1))
                mp_drawing.draw_landmarks(
                    image_bgr, results.left_hand_landmarks, mp_holistic.HAND_CONNECTIONS,
                    landmark_drawing_spec=mp_drawing.DrawingSpec(color=RED, thickness=2, circle_radius=2))
                mp_drawing.draw_landmarks(
                    image_bgr, results.right_hand_landmarks, mp_holistic.HAND_CONNECTIONS,
                    landmark_drawing_spec=mp_drawing.DrawingSpec(color=BLUE, thickness=2, circle_radius=2))

                # ★★★ 修正: COLOR_BGR_RGB -> COLOR_BGR2RGB ★★★
                image_rgb_cam = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
                image_pygame = pygame.image.frombuffer(image_rgb_cam.tobytes(), image_rgb_cam.shape[1::-1], "RGB")
                camera_surface_scaled = pygame.transform.scale(image_pygame, (CAM_PANEL_RECT.width, CAM_PANEL_RECT.height))


        # 4. ★★★ 格闘ゲーム ジェスチャーロジック ★★★
        
        current_left_elbow_angle = 180
        current_right_elbow_angle = 180
        is_left_open = False
        is_right_open = False

        # ★★★ 修正: results が None でないかチェック ★★★
        if results and results.pose_landmarks:
            landmarks = results.pose_landmarks.landmark
            # 左肘
            current_left_elbow_angle = calculate_angle(
                landmarks[mp_holistic.PoseLandmark.LEFT_SHOULDER],
                landmarks[mp_holistic.PoseLandmark.LEFT_ELBOW],
                landmarks[mp_holistic.PoseLandmark.LEFT_WRIST]
            )
            # 右肘
            current_right_elbow_angle = calculate_angle(
                landmarks[mp_holistic.PoseLandmark.RIGHT_SHOULDER],
                landmarks[mp_holistic.PoseLandmark.RIGHT_ELBOW],
                landmarks[mp_holistic.PoseLandmark.RIGHT_WRIST]
            )

        # ★★★ 修正: results が None でないかチェック ★★★
        if results and results.left_hand_landmarks:
            is_left_open = is_hand_open(results.left_hand_landmarks)
        if results and results.right_hand_landmarks:
            is_right_open = is_hand_open(results.right_hand_landmarks)

        # プレイヤー状態タイマー更新
        if player_state_timer > 0:
            player_state_timer -= delta_time_ms
        else:
            player_state = 'kihon'
            guard_duration_ms = 0 # 状態がリセットされたらガード維持時間もリセット

        # (1) 防御判定 (最優先)
        # ★★★ 修正: 角度のロジックを > から < に変更 ★★★
        if player_state == 'kihon' and \
           current_left_elbow_angle < GUARD_ANGLE and \
           current_right_elbow_angle < GUARD_ANGLE:
            
            player_state = 'guard'
            guard_start_time = pygame.time.get_ticks()
            guard_duration_ms = 0

        # (2) 防御継続判定
        if player_state == 'guard':
            # ★★★ 修正: 角度のロジックを > から < に変更 ★★★
            if current_left_elbow_angle < GUARD_ANGLE and current_right_elbow_angle < GUARD_ANGLE:
                guard_duration_ms = pygame.time.get_ticks() - guard_start_time
                # 5秒維持ボーナス
                if guard_duration_ms >= 5000:
                    add_log("Guard Bonus! HP+100, E+1")
                    player_hp = min(PLAYER_MAX_HP, player_hp + 100)
                    player_energy = min(PLAYER_MAX_ENERGY, player_energy + 1)
                    guard_start_time = pygame.time.get_ticks() # タイマーリセット
            else:
                player_state = 'kihon' # 防御解除
                guard_duration_ms = 0

        # (3) 攻撃判定 (kihon状態の時のみ)
        if player_state == 'kihon':
            
            # ★★★ 修正: 腕の「曲→伸」判定ロジックを変更 ★★★
            left_arm_extended = (prev_left_elbow_angle < ELBOW_ANGLE_BENT) and (current_left_elbow_angle > ELBOW_ANGLE_STRAIGHT)
            right_arm_extended = (prev_right_elbow_angle < ELBOW_ANGLE_BENT) and (current_right_elbow_angle > ELBOW_ANGLE_STRAIGHT)

            # 波動 (両手パー + 両腕伸ばし + エナジー5)
            if is_left_open and is_right_open and (left_arm_extended or right_arm_extended) and player_energy >= 5:
                player_state = 'hado'
                player_state_timer = 1500 # 1.5秒硬直
                player_energy -= 5
                add_log("HADO! (E-5)")
                # 弾生成 (アニメーションは描画側で)
                bullet_rect = img_hado_bullets[0].get_rect(midleft=(player_rect.right, player_rect.centery))
                player_bullets.append([bullet_rect, 'hado', 15, 0])

            # 気弾 (片手パー + 片腕伸ばし + エナジー2)
            elif (is_left_open and left_arm_extended) != (is_right_open and right_arm_extended) and player_energy >= 2:
                player_state = 'kikouha'
                player_state_timer = 1000 # 1秒硬直
                player_energy -= 2
                add_log("KIKOUHA! (E-2)")
                bullet_rect = img_kidan[0].get_rect(midleft=(player_rect.right, player_rect.centery))
                player_bullets.append([bullet_rect, 'kidan', 20, 0])

            # パンチ (片手グー + 片腕伸ばし + エナジー1)
            elif player_energy >= 1:
                if (not is_left_open) and left_arm_extended:
                    player_state = 'punch_left'
                    player_state_timer = 1000 # 1秒硬直
                    player_energy -= 1
                    add_log("LEFT PUNCH! (E-1)")
                    enemy_hp -= 100
                    hit_effects.append([img_dageki_dm, img_dageki_dm.get_rect(center=enemy_rect.center), 200]) # 0.2秒
                
                elif (not is_right_open) and right_arm_extended:
                    player_state = 'punch_right'
                    player_state_timer = 1000 # 1秒硬直
                    player_energy -= 1
                    add_log("RIGHT PUNCH! (E-1)")
                    enemy_hp -= 100
                    hit_effects.append([img_dageki_dm, img_dageki_dm.get_rect(center=enemy_rect.center), 200]) # 0.2秒


        # 判定用に現在の角度を保存
        prev_left_elbow_angle = current_left_elbow_angle
        prev_right_elbow_angle = current_right_elbow_angle


        # 5. ★★★ ゲームロジック更新 ★★★
        
        # (1) 敵の回復
        enemy_heal_timer += delta_time_ms
        if enemy_heal_timer >= 1000: # 1秒ごと
            enemy_heal_timer = 0
            if enemy_hp < ENEMY_MAX_HP and enemy_heal_count > 0:
                heal_amount = int(enemy_hp * 0.03)
                enemy_hp = min(ENEMY_MAX_HP, enemy_hp + heal_amount)
                enemy_heal_count -= 1
                # add_log(f"Enemy heals {heal_amount} HP (Left: {enemy_heal_count})")

        # (2) 敵の攻撃
        enemy_attack_timer += delta_time_ms
        if enemy_attack_timer >= enemy_next_attack_time:
            enemy_attack_timer = 0
            enemy_next_attack_time = random.randint(5000, 10000) # 次の攻撃時間
            num_balls = random.randint(1, 5)
            add_log(f"Enemy attacks! ({num_balls} balls)")
            for _ in range(num_balls):
                ball_rect = img_ball.get_rect(center=enemy_rect.center)
                # プレイヤーへのベクトル計算
                dx = player_rect.centerx - enemy_rect.centerx
                dy = player_rect.centery - enemy_rect.centery
                dist = math.hypot(dx, dy)
                if dist == 0: dist = 1
                vx = (dx / dist) * 10 # 速度10
                vy = (dy / dist) * 10
                enemy_bullets.append([ball_rect, vx, vy])

        # ★★★ 修正: 弾の当たり判定と相殺ロジックを修正 ★★★
        # (3) プレイヤーの弾の移動と当たり判定
        for bullet in player_bullets[:]: # コピーをループ
            bullet[0].x += bullet[2] # speed
            # 弾アニメーション (気弾/波動)
            if bullet[1] == 'kidan':
                bullet[3] = (bullet[3] + 0.2) % len(img_kidan) # アニメ速度
            elif bullet[1] == 'hado':
                # ★★★ 修正: 波動アニメーションロジック ★★★
                bullet[3] += 0.2 # animation_frame (float)
                if bullet[3] >= len(img_hado_animation_list):
                    bullet[3] = len(img_hado_animation_list) - 1 # 最後のフレーム (hado4) で止める

            # 敵との当たり判定
            if bullet[0].colliderect(enemy_rect):
                if bullet[1] == 'kidan':
                    enemy_hp -= 400 # (★ ユーザーのコードスニペットに基づき 200->400)
                    hit_effects.append([img_kidan_dm, img_kidan_dm.get_rect(center=enemy_rect.center), 200])
                elif bullet[1] == 'hado':
                    enemy_hp -= 1000 # (★ ユーザーのコードスニペットに基づき 500->1000)
                    hit_effects.append([img_hado_dm, img_hado_dm.get_rect(center=enemy_rect.center), 200])
                player_bullets.remove(bullet)
                continue # この弾は消えたので次の弾へ
            
            # 画面外
            if bullet[0].left > GAME_PANEL_WIDTH:
                player_bullets.remove(bullet)
                continue # この弾は消えたので次の弾へ
            
            # 敵の弾との相殺 (気弾のみ)
            if bullet[1] == 'kidan':
                collided_with_enemy_ball = False
                for enemy_ball in enemy_bullets[:]:
                    if bullet[0].colliderect(enemy_ball[0]):
                        # ★★★ 修正: 相殺時にエフェクト追加 ★★★
                        collision_point = bullet[0].center
                        hit_effects.append([img_kidan_dm, img_kidan_dm.get_rect(center=collision_point), 200]) # 0.2秒
                        player_bullets.remove(bullet)
                        enemy_bullets.remove(enemy_ball)
                        add_log("Offset!")
                        collided_with_enemy_ball = True
                        break # 内側のループを抜ける (この弾はもうない)
                
                if collided_with_enemy_ball:
                    continue # この弾は相殺削除されたので、次の弾へ


        # (4) 敵の弾の移動と当たり判定
        for ball in enemy_bullets[:]:
            ball[0].x += ball[1] # vx
            ball[0].y += ball[2] # vy
            
            # ガード判定
            if player_state == 'guard' and ball[0].colliderect(guard_rect):
                enemy_bullets.remove(ball)
                add_log("Guarded!")
                continue
            
            # プレイヤー当たり判定
            if ball[0].colliderect(player_rect):
                player_hp -= 200
                enemy_bullets.remove(ball)
                add_log("Hit! (HP-200)")
                continue

            # 画面外
            if ball[0].right < 0 or ball[0].top > GAME_HEIGHT or ball[0].bottom < 0:
                enemy_bullets.remove(ball)

        # (5) ヒットエフェクトのタイマー更新
        for effect in hit_effects[:]:
            effect[2] -= delta_time_ms # timer
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
            add_log("You Lose...") # (★ ユーザーのコードスニペットに基づき変更)
        elif enemy_hp <= 0:
            game_finished = True
            game_won = True
            add_log("Win!!") # (★ ユーザーのコードスニペットに基づき変更)


        # 6. ★★★ Pygame ゲーム画面描画 ★★★
        
        game_surface = screen.subsurface(GAME_PANEL_RECT)
        game_surface.fill(SKY_BLUE) # 背景

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
            game_surface.blit(img_kihon, player_rect) # ガード中も本体表示
            game_surface.blit(img_guard, guard_rect) # ガードエフェクト

        # 敵描画
        game_surface.blit(img_enemy, enemy_rect)
        
        # プレイヤーの弾 描画
        for bullet in player_bullets:
            if bullet[1] == 'kidan':
                game_surface.blit(img_kidan[int(bullet[3])], bullet[0])
            elif bullet[1] == 'hado':
                # ★★★ 修正: 波動アニメーションリストから描画 ★★★
                frame_index = int(bullet[3])
                game_surface.blit(img_hado_animation_list[frame_index], bullet[0])

        # 敵の弾 描画
        for ball in enemy_bullets:
            game_surface.blit(img_ball, ball[0])

        # エフェクト 描画
        for effect in hit_effects:
            game_surface.blit(effect[0], effect[1]) # img, rect

        # HP/エナジーバー 描画
        # プレイヤーHP
        draw_bar(game_surface, pygame.Rect(player_rect.left, player_rect.top - 30, player_rect.width, 20), player_hp, PLAYER_MAX_HP, GREEN)
        # プレイヤーエナジー
        draw_bar(game_surface, pygame.Rect(player_rect.left, player_rect.top - 55, player_rect.width, 20), player_energy, PLAYER_MAX_ENERGY, BLUE)
        # 敵HP
        draw_bar(game_surface, pygame.Rect(enemy_rect.left, enemy_rect.top - 30, enemy_rect.width, 20), enemy_hp, ENEMY_MAX_HP, RED)


    # --- ★★★ UIパネルの描画 (全状態共通) ★★★ ---

    # --- スコアパネル (左上) ---
    score_surface = screen.subsurface(SCORE_PANEL_RECT)
    score_surface.fill(BLACK)
    title_text = font_title.render("STATUS", True, WHITE)
    score_surface.blit(title_text, (10, 10))
    
    player_hp_text = font_ui.render(f"Player HP: {player_hp}", True, GREEN)
    score_surface.blit(player_hp_text, (15, 60))

    # (★ ユーザーのコードスニペットに基づき色を ORANGE に変更)
    player_en_text = font_ui.render(f"Energy: {player_energy}", True, ORANGE)
    score_surface.blit(player_en_text, (15, 100))

    enemy_hp_text = font_ui.render(f"Enemy HP: {enemy_hp}", True, RED)
    score_surface.blit(enemy_hp_text, (15, 140))
    
    enemy_heal_text = font_ui.render(f"Heal: {enemy_heal_count}", True, WHITE)
    score_surface.blit(enemy_heal_text, (15, 180))


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
    pygame.draw.rect(cam_surface, BLACK, (0, 0, CAM_PANEL_RECT.width, CAM_PANEL_RECT.height)) # 背景を黒で
    cam_surface.blit(cam_title, (10, 10)) # タイトルを描画

    # ★★★ 修正: カメラパネルの表示ロジックを修正 ★★★
    if not game_finished:
        if cap.isOpened() and camera_surface_scaled:
            # 正常時：カメラ映像を表示
            cam_surface.blit(camera_surface_scaled, (0, 30))
        elif not cap.isOpened():
            # 異常時：エラーメッセージを表示
            cam_error_text = font_log.render("Camera not found.", True, RED)
            cam_surface.blit(cam_error_text, (10, 50))
        # (camera_surface_scaled が None の場合＝フレーム読み取り失敗時は、黒背景のまま)

    # 画面更新 (全状態共通)
    pygame.display.flip()
    clock.tick(30) # 負荷を考慮し、少しフレームレートを落とす (60でも可)

# --- 終了処理 ---
if cap.isOpened():
    cap.release()
cv2.destroyAllWindows()
pygame.quit()


