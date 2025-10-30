import cv2
import mediapipe as mp
import pygame
import math
import random
import numpy as np # カメラ映像変換に必要
import sys # 終了処理用にインポート

# --- 初期設定 ---

# MediaPipeの手検出モデルと描画ツールを準備
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
hands = mp_hands.Hands(
    max_num_hands=2, # 両手使えるように
    min_detection_confidence=0.7,
    min_tracking_confidence=0.7
)

# Pygameの初期化
pygame.init()
pygame.font.init()

# --- 画面レイアウト定義 ---
SCREEN_WIDTH, SCREEN_HEIGHT = 1280, 720
LEFT_PANEL_WIDTH = int(SCREEN_WIDTH * 0.2)
GAME_PANEL_WIDTH = SCREEN_WIDTH - LEFT_PANEL_WIDTH
GAME_HEIGHT = SCREEN_HEIGHT

SCORE_PANEL_RECT = pygame.Rect(0, 0, LEFT_PANEL_WIDTH, int(SCREEN_HEIGHT * 0.4))
LOG_PANEL_RECT = pygame.Rect(0, SCORE_PANEL_RECT.height, LEFT_PANEL_WIDTH, int(SCREEN_HEIGHT * 0.3))
CAM_PANEL_RECT = pygame.Rect(0, SCORE_PANEL_RECT.height + LOG_PANEL_RECT.height, LEFT_PANEL_WIDTH, int(SCREEN_HEIGHT * 0.3))
GAME_PANEL_RECT = pygame.Rect(LEFT_PANEL_WIDTH, 0, GAME_PANEL_WIDTH, GAME_HEIGHT)

# --- ★ つららクラス ---
class Icicle(pygame.sprite.Sprite):
    def __init__(self, image):
        super().__init__()
        self.image = image
        self.rect = self.image.get_rect()
        self.reset()

    def reset(self):
        # 画面上部中央に配置
        self.rect.centerx = GAME_PANEL_WIDTH // 2
        self.rect.bottom = 100 # 上端よりさらに上に配置
        self.velocity_y = 0.0 # 初速度

    def update(self, gravity_accel):
        # 重力加速度を適用
        self.velocity_y += gravity_accel
        self.rect.y += int(self.velocity_y)

    def draw(self, surface):
        surface.blit(self.image, self.rect)

# --- ゲーム設定と物理定義 ---
PIXELS_PER_METER = 360 # 参考値 (重力計算に使用)
FPS = 60 # フレームレート

# ★ 重力オプション辞書 (名前: m/s^2)
GRAVITY_OPTIONS = {
    "Sun": 274.0, #太陽
    "Earth": 9.8, #地球
    "Mars": 3.7, #火星
    "Venus": 8.87, #金星
    "Jupiter": 24.79, #木星
    "Saturn": 10.44, #土星
    "Uranus": 8.69, #天王星
    "Neptune": 11.15, #海王星
}
# ★ 選択中の重力キーと計算後の加速度
selected_gravity_key = "Earth"
GRAVITY_ACCEL = (GRAVITY_OPTIONS[selected_gravity_key] * PIXELS_PER_METER) / (FPS * FPS)

# Pygameウィンドウの設定
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Icicle Catch Game")

# 色とフォントの定義
WHITE = (255, 255, 255)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLACK = (0, 0, 0)
GRAY = (50, 50, 50)
SKY_BLUE = (135, 206, 235)
BLUE = (0, 0, 255)
ORANGE = (255, 165, 0)
BUTTON_COLOR = (0, 100, 200)
BUTTON_HOVER_COLOR = (0, 150, 255)
BUTTON_TEXT_COLOR = WHITE
RADIO_BUTTON_COLOR = WHITE
RADIO_BUTTON_SELECTED_COLOR = GREEN

font_ui = pygame.font.Font(None, 36)
font_log = pygame.font.Font(None, 24)
font_title = pygame.font.Font(None, 40)
game_over_font = pygame.font.Font(None, 100)
result_text_font = pygame.font.Font(None, 80)
button_font = pygame.font.Font(None, 50)
button_font_small = pygame.font.Font(None, 30)
# ★ ラジオボタン用フォント
radio_font = pygame.font.Font(None, 22)


# --- アセット読み込み ---

# ★ つらら画像の読み込み
icicle_image = None
try:
    img = pygame.image.load("image/turara.png").convert_alpha()
    icicle_image = img
except FileNotFoundError:
    print("エラー: image/turara.png が見つかりません。")
    pygame.quit()
    sys.exit()

# ★ ダンサーアニメーション画像の読み込み (成功画面用)
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

# --- ゲームオブジェクト ---
icicle = Icicle(icicle_image) if icicle_image else None

# プレイヤー（カーソル）の設定
left_cursor_pos = [-100, -100]
right_cursor_pos = [-100, -100]
cursor_radius = 45
left_is_open_current = True
right_is_open_current = True
left_was_open = True
right_was_open = True

# Webカメラの準備
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("エラー: カメラを起動できません。")

# --- ゲーム状態管理 ---
game_state = 'READY' # 'READY', 'WAITING', 'DROPPING', 'CAUGHT', 'MISSED'
drop_delay_ms = 0

# --- タイマー変数 ---
start_time = 0
elapsed_time = 0
final_time = 0

# --- UI要素 ---
start_button_rect_screen = pygame.Rect(0, 0, 200, 80)
start_button_rect_screen.center = (GAME_PANEL_RECT.centerx, GAME_PANEL_RECT.centery)
retry_button_rect_screen = pygame.Rect(0, 0, 300, 60)
retry_button_rect_screen.center = (GAME_PANEL_RECT.centerx, GAME_PANEL_RECT.bottom - 80)

# ★ ラジオボタンのRect辞書
radio_button_rects = {}
radio_y_start = 100
radio_y_offset = 25
radio_x_pos = 15
radio_radius = 8
label_x_offset = 20

for i, key in enumerate(GRAVITY_OPTIONS.keys()):
    center_y = SCORE_PANEL_RECT.top + radio_y_start + i * radio_y_offset
    # クリック判定用のRectを作成 (少し大きめに)
    rect = pygame.Rect(radio_x_pos - radio_radius - 2, center_y - radio_radius - 2, (radio_radius + 2) * 2 + 150, (radio_radius + 2) * 2) # ラベル部分まで含む
    radio_button_rects[key] = rect


# --- 説明テキスト ---
instructions = [
    "--- Icicle Catch ---",
    "1. Put your hand over",
    "   the START button.",
    "2. Close your hand to",
    "   start the game.",
    "3. Icicle drops after",
    "   5-10 sec.",
    "4. Catch it by closing",
    "   your hand!",
]

# --- 関数定義 ---

def is_hand_open(hand_landmarks):
    tip_ids = [mp_hands.HandLandmark.INDEX_FINGER_TIP, mp_hands.HandLandmark.MIDDLE_FINGER_TIP, mp_hands.HandLandmark.RING_FINGER_TIP, mp_hands.HandLandmark.PINKY_TIP]
    pip_ids = [mp_hands.HandLandmark.INDEX_FINGER_PIP, mp_hands.HandLandmark.MIDDLE_FINGER_PIP, mp_hands.HandLandmark.RING_FINGER_PIP, mp_hands.HandLandmark.PINKY_PIP]
    open_fingers = sum(1 for tip_id, pip_id in zip(tip_ids, pip_ids) if hand_landmarks.landmark[tip_id].y < hand_landmarks.landmark[pip_id].y)
    return open_fingers >= 3

def format_time(ms):
    total_seconds = ms // 1000
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    milliseconds = (ms % 1000) // 10
    return f"{minutes:02}:{seconds:02}.{milliseconds:02}"

# ★ 重力加速度を計算する関数
def calculate_gravity_accel(key):
    gravity_ms2 = GRAVITY_OPTIONS.get(key, 9.8) # 見つからなければ地球の重力
    return (gravity_ms2 * PIXELS_PER_METER) / (FPS * FPS)

# ★ ゲームリセット関数
def reset_game():
    global game_state, elapsed_time, final_time, drop_delay_ms, icicle, start_time, left_is_open_current, right_is_open_current, left_was_open, right_was_open, selected_gravity_key, GRAVITY_ACCEL
    game_state = 'READY'
    elapsed_time = 0
    final_time = 0
    drop_delay_ms = 0
    if icicle:
        icicle.reset()
    start_time = 0
    left_is_open_current = True
    right_is_open_current = True
    left_was_open = True
    right_was_open = True
    # ★ 重力を地球に戻す
    selected_gravity_key = "Earth"
    GRAVITY_ACCEL = calculate_gravity_accel(selected_gravity_key)
    global cap
    if not cap.isOpened():
       cap = cv2.VideoCapture(0)
       if cap.isOpened():
           print("Camera reopened for retry.")
       else:
           print("Error: Failed to reopen camera for retry.")


# --- メインループ ---
running = True
clock = pygame.time.Clock()
camera_surface_scaled = None

while running:

    delta_time_ms = clock.tick(FPS)
    mouse_pos = pygame.mouse.get_pos()
    mouse_click = False

    # 1. イベント処理
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                running = False
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                mouse_click = True

    # 画面全体をクリア
    screen.fill(GRAY)

    # --- カメラ処理 & 手の検出 (常に実行) ---
    left_closed_this_frame = False
    right_closed_this_frame = False
    results = None
    hand_detected = False

    if cap.isOpened():
        success, image_cam = cap.read()
        if success:
            image_rgb = cv2.cvtColor(cv2.flip(image_cam, 1), cv2.COLOR_BGR2RGB)
            image_rgb.flags.writeable = False
            results = hands.process(image_rgb)
            image_rgb.flags.writeable = True

            image_bgr = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
            if results and results.multi_hand_landmarks:
                hand_detected = True
                for hand_landmarks in results.multi_hand_landmarks:
                    mp_drawing.draw_landmarks(image_bgr, hand_landmarks, mp_hands.HAND_CONNECTIONS)

            image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
            image_pygame = pygame.image.frombuffer(image_rgb.tobytes(), image_rgb.shape[1::-1], "RGB")
            camera_surface_scaled = pygame.transform.scale(image_pygame, (CAM_PANEL_RECT.width, CAM_PANEL_RECT.height))

            left_is_open_now = True
            right_is_open_now = True
            left_cursor_pos[:] = [-100, -100]
            right_cursor_pos[:] = [-100, -100]

            if results and results.multi_hand_landmarks:
                for hand_landmarks, handedness in zip(results.multi_hand_landmarks, results.multi_handedness):
                    is_open = is_hand_open(hand_landmarks)
                    mcp_landmark = hand_landmarks.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_MCP]
                    hand_pos = (int(mcp_landmark.x * GAME_PANEL_WIDTH), int(mcp_landmark.y * GAME_HEIGHT))

                    if handedness.classification[0].label == 'Left':
                        left_cursor_pos[:] = hand_pos
                        left_is_open_now = is_open
                    elif handedness.classification[0].label == 'Right':
                        right_cursor_pos[:] = hand_pos
                        right_is_open_now = is_open

            left_closed_this_frame = left_was_open and not left_is_open_now
            right_closed_this_frame = right_was_open and not right_is_open_now

            left_was_open = left_is_open_now
            right_was_open = right_is_open_now
            left_is_open_current = left_is_open_now
            right_is_open_current = right_is_open_now

        else:
             if cap.isOpened():
                 print("Warning: Failed to read frame from camera.")
             left_cursor_pos[:] = [-100, -100]
             right_cursor_pos[:] = [-100, -100]

    else:
        left_is_open_current = True
        right_is_open_current = True
        left_cursor_pos[:] = [-100, -100]
        right_cursor_pos[:] = [-100, -100]


    # --- ゲームロジック (状態に基づいて実行) ---

    left_cursor_rect_game = pygame.Rect(left_cursor_pos[0] - cursor_radius, left_cursor_pos[1] - cursor_radius, cursor_radius * 2, cursor_radius * 2)
    right_cursor_rect_game = pygame.Rect(right_cursor_pos[0] - cursor_radius, right_cursor_pos[1] - cursor_radius, cursor_radius * 2, cursor_radius * 2)
    start_button_rect_game = start_button_rect_screen.copy()
    start_button_rect_game.center = (start_button_rect_screen.centerx - GAME_PANEL_RECT.left, start_button_rect_screen.centery - GAME_PANEL_RECT.top)
    retry_button_rect_game = retry_button_rect_screen.copy()
    retry_button_rect_game.center = (retry_button_rect_screen.centerx - GAME_PANEL_RECT.left, retry_button_rect_screen.centery - GAME_PANEL_RECT.top)

    # ★ ラジオボタンのクリック処理 (どの状態でも変更可能)
    if mouse_click:
        for key, rect in radio_button_rects.items():
            # マウス座標はスクリーン全体なのでそのまま使う
            if rect.collidepoint(mouse_pos):
                if selected_gravity_key != key:
                    selected_gravity_key = key
                    GRAVITY_ACCEL = calculate_gravity_accel(key)
                    print(f"Gravity changed to: {key} ({GRAVITY_OPTIONS[key]:.2f} m/s^2)")
                    # もしゲーム中なら影響を与える
                    if game_state == 'DROPPING' and icicle:
                        # 速度に影響を与えるか、あるいはリセットするか
                        # ここではリセットせずにそのまま継続
                        pass
                break # 他のボタンはチェックしない


    if game_state == 'READY':
        start_activated = False
        if left_closed_this_frame and start_button_rect_game.colliderect(left_cursor_rect_game):
            start_activated = True
        elif right_closed_this_frame and start_button_rect_game.colliderect(right_cursor_rect_game):
            start_activated = True
        
        # 2. ★ マウスクリックでスタート (ここから追加)
        mouse_x_in_game = mouse_pos[0] - GAME_PANEL_RECT.left
        mouse_y_in_game = mouse_pos[1] - GAME_PANEL_RECT.top
        
        # ゲームパネル内でのクリックかをまず確認
        if GAME_PANEL_RECT.collidepoint(mouse_pos):
             # ゲームパネル内座標のスタートボタンRectと衝突判定
             if start_button_rect_game.collidepoint(mouse_x_in_game, mouse_y_in_game) and mouse_click:
                  start_activated = True # ★ クリックでもアクティベート
        # ★ (ここまで追加)

        if start_activated:
            game_state = 'WAITING'
            start_time = pygame.time.get_ticks()
            elapsed_time = 0
            drop_delay_ms = random.randint(5000, 10000)
            if icicle: icicle.reset()

    elif game_state == 'WAITING':
        elapsed_time = pygame.time.get_ticks() - start_time
        if elapsed_time >= drop_delay_ms:
            game_state = 'DROPPING'

    elif game_state == 'DROPPING':
        elapsed_time = pygame.time.get_ticks() - start_time
        if icicle:
            icicle.update(GRAVITY_ACCEL) # ★ 現在選択中の重力を使う
            if icicle.rect.top > GAME_HEIGHT:
                game_state = 'MISSED'
                final_time = elapsed_time
                if cap.isOpened():
                    # ★ カメラは閉じない
                    # cap.release()
                    print("Game over.")

            icicle_rect_game = icicle.rect

            caught = False
            if left_closed_this_frame and left_cursor_rect_game.colliderect(icicle_rect_game):
                caught = True
            elif right_closed_this_frame and right_cursor_rect_game.colliderect(icicle_rect_game):
                caught = True

            if caught:
                game_state = 'CAUGHT'
                final_time = elapsed_time
                if cap.isOpened():
                    # ★ カメラは閉じない
                    # cap.release()
                    print("Icicle caught!")

    elif game_state == 'CAUGHT' or game_state == 'MISSED':
        # ★ マウスクリックでリトライ
        mouse_x_in_game = mouse_pos[0] - GAME_PANEL_RECT.left
        mouse_y_in_game = mouse_pos[1] - GAME_PANEL_RECT.top

        if GAME_PANEL_RECT.collidepoint(mouse_pos):
             if retry_button_rect_game.collidepoint(mouse_x_in_game, mouse_y_in_game) and mouse_click:
                  reset_game()


    # --- 描画処理 ---

    # --- ゲームパネル (右側) ---
    game_surface = screen.subsurface(GAME_PANEL_RECT)
    game_surface.fill(SKY_BLUE)

    if game_state == 'CAUGHT':
        result_text = result_text_font.render("Success!!", True, ORANGE)
        game_surface.blit(result_text, result_text.get_rect(center=(GAME_PANEL_WIDTH // 2, GAME_HEIGHT // 4)))
        time_text = font_ui.render(f"Catch Time: {format_time(final_time)}", True, BLACK)
        game_surface.blit(time_text, time_text.get_rect(center=(GAME_PANEL_WIDTH // 2, GAME_HEIGHT // 4 + 70)))

        if dancer_images:
            dancer_frame_time += delta_time_ms
            if dancer_frame_time > ANIMATION_SPEED_MS:
                dancer_frame = (dancer_frame + 1) % len(dancer_images)
                dancer_frame_time = 0
            current_dancer_image = dancer_images[dancer_frame]
            img_rect = current_dancer_image.get_rect(center=(GAME_PANEL_WIDTH // 2, GAME_HEIGHT // 2 + 100))
            game_surface.blit(current_dancer_image, img_rect)

        mouse_x_in_game = mouse_pos[0] - GAME_PANEL_RECT.left
        mouse_y_in_game = mouse_pos[1] - GAME_PANEL_RECT.top
        is_hovering_retry = retry_button_rect_game.collidepoint(mouse_x_in_game, mouse_y_in_game)

        btn_color = BUTTON_HOVER_COLOR if is_hovering_retry else BUTTON_COLOR
        pygame.draw.rect(game_surface, btn_color, retry_button_rect_game, border_radius=10)
        btn_text = button_font_small.render("Retry Challenge", True, BUTTON_TEXT_COLOR)
        game_surface.blit(btn_text, btn_text.get_rect(center=retry_button_rect_game.center))

    elif game_state == 'MISSED':
        go_text = game_over_font.render("GAME OVER", True, RED)
        game_surface.blit(go_text, go_text.get_rect(center=(GAME_PANEL_WIDTH // 2, GAME_HEIGHT // 2 - 50)))
        time_text = font_ui.render(f"Final Time: {format_time(final_time)}", True, WHITE) # Game Over時は白文字
        game_surface.blit(time_text, time_text.get_rect(center=(GAME_PANEL_WIDTH // 2, GAME_HEIGHT // 2 + 50)))

        mouse_x_in_game = mouse_pos[0] - GAME_PANEL_RECT.left
        mouse_y_in_game = mouse_pos[1] - GAME_PANEL_RECT.top
        is_hovering_retry = retry_button_rect_game.collidepoint(mouse_x_in_game, mouse_y_in_game)

        btn_color = BUTTON_HOVER_COLOR if is_hovering_retry else BUTTON_COLOR
        pygame.draw.rect(game_surface, btn_color, retry_button_rect_game, border_radius=10)
        btn_text = button_font_small.render("Retry Challenge", True, BUTTON_TEXT_COLOR)
        game_surface.blit(btn_text, btn_text.get_rect(center=retry_button_rect_game.center))

    else: # READY, WAITING, DROPPING
        if icicle and (game_state == 'WAITING' or game_state == 'DROPPING'):
             icicle.draw(game_surface)

        if game_state == 'READY':
            is_hovering_start = start_button_rect_game.colliderect(left_cursor_rect_game) or start_button_rect_game.colliderect(right_cursor_rect_game)
            btn_color = BUTTON_HOVER_COLOR if is_hovering_start else BUTTON_COLOR
            pygame.draw.rect(game_surface, btn_color, start_button_rect_game, border_radius=10)
            btn_text = button_font.render("START", True, BUTTON_TEXT_COLOR)
            game_surface.blit(btn_text, btn_text.get_rect(center=start_button_rect_game.center))

        left_cursor_color = GREEN if not left_is_open_current else RED # 閉じていたら緑
        right_cursor_color = GREEN if not right_is_open_current else RED # 閉じていたら緑
        ALPHA_VALUE = 128

        if left_cursor_pos[0] != -100:
            circle_surface_left = pygame.Surface((cursor_radius * 2, cursor_radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(circle_surface_left, left_cursor_color + (ALPHA_VALUE,), (cursor_radius, cursor_radius), cursor_radius)
            game_surface.blit(circle_surface_left, (left_cursor_pos[0] - cursor_radius, left_cursor_pos[1] - cursor_radius)) # ゲーム座標基準

        if right_cursor_pos[0] != -100:
            circle_surface_right = pygame.Surface((cursor_radius * 2, cursor_radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(circle_surface_right, right_cursor_color + (ALPHA_VALUE,), (cursor_radius, cursor_radius), cursor_radius)
            game_surface.blit(circle_surface_right, (right_cursor_pos[0] - cursor_radius, right_cursor_pos[1] - cursor_radius)) # ゲーム座標基準


    # --- UIパネルの描画 ---

    # --- スコアパネル (左上) ---
    score_surface = screen.subsurface(SCORE_PANEL_RECT)
    score_surface.fill(BLACK)
    title_text = font_title.render("TIMER / GRAVITY", True, WHITE) # タイトル変更
    score_surface.blit(title_text, (10, 10))

    display_time = elapsed_time if final_time == 0 else final_time
    time_text = font_ui.render(f"{format_time(display_time)}", True, WHITE)
    score_surface.blit(time_text, (15, 60))

    # ★ ラジオボタン描画
    radio_y = radio_y_start
    for key in GRAVITY_OPTIONS.keys():
        center_y = SCORE_PANEL_RECT.top + radio_y
        center_x = SCORE_PANEL_RECT.left + radio_x_pos

        # ボタンの円
        pygame.draw.circle(score_surface, RADIO_BUTTON_COLOR, (center_x, center_y), radio_radius, 1) # 枠線
        if key == selected_gravity_key:
            pygame.draw.circle(score_surface, RADIO_BUTTON_SELECTED_COLOR, (center_x, center_y), radio_radius - 3) # 内側の塗りつぶし

        # ラベル
        label_text = radio_font.render(f"{key} ({GRAVITY_OPTIONS[key]:.2f} m/s²)", True, WHITE)
        score_surface.blit(label_text, (center_x + label_x_offset, center_y - label_text.get_height() // 2))

        radio_y += radio_y_offset


    # --- 説明パネル (左中) ---
    log_surface = screen.subsurface(LOG_PANEL_RECT)
    log_surface.fill(BLACK)
    log_title = font_title.render("HOW TO PLAY", True, WHITE)
    log_surface.blit(log_title, (10, 10))
    y_pos = 50
    for line in instructions:
        log_text = font_log.render(line, True, GREEN)
        log_surface.blit(log_text, (15, y_pos))
        y_pos += 25

    # --- カメラパネル (左下) ---
    cam_surface = screen.subsurface(CAM_PANEL_RECT)
    pygame.draw.rect(cam_surface, BLACK, (0, 0, CAM_PANEL_RECT.width, CAM_PANEL_RECT.height))
    cam_title = font_title.render("CAMERA", True, WHITE)
    cam_surface.blit(cam_title, (10, 10))

    if cap.isOpened() and camera_surface_scaled:
        cam_surface.blit(camera_surface_scaled, (0, 30))
    elif not cap.isOpened(): # カメラが開いていない場合
         # ★ どの状態でもエラー表示しない（リトライ時に再オープンするため）
         # if game_state not in ['CAUGHT', 'MISSED']:
         #     cam_error_text = font_log.render("Camera not found.", True, RED)
         #     cam_surface.blit(cam_error_text, (10, 50))
         pass # エラーメッセージは不要

    # 画面更新
    pygame.display.flip()

# --- 終了処理 ---
if cap.isOpened():
    cap.release()
cv2.destroyAllWindows()
pygame.quit()
sys.exit()
