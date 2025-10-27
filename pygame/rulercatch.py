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
        self.rect.bottom = 0 # 上端よりさらに上に配置
        self.velocity_y = 0.0 # 初速度

    def update(self, gravity_accel):
        # 重力加速度を適用
        self.velocity_y += gravity_accel
        self.rect.y += int(self.velocity_y)

    def draw(self, surface):
        surface.blit(self.image, self.rect)

# --- ゲーム設定と物理定義 ---
PIXELS_PER_METER = 360 # 参考値 (重力計算に使用)
GRAVITY_MS2 = 9.8  # 現実の重力加速度 m/s^2　9.8
GRAVITY_PIXELS_S2 = GRAVITY_MS2 * PIXELS_PER_METER # ピクセル/s^2
FPS = 60 # フレームレート
GRAVITY_ACCEL = GRAVITY_PIXELS_S2 / (FPS * FPS) # ピクセル/フレーム^2 (約0.98)

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
BUTTON_HOVER_COLOR = (0, 150, 255) # ★ ボタン上でホバーする色 (手のカーソル用/マウス用)
BUTTON_TEXT_COLOR = WHITE

font_ui = pygame.font.Font(None, 36)
font_log = pygame.font.Font(None, 24)
font_title = pygame.font.Font(None, 40)
game_over_font = pygame.font.Font(None, 100)
result_text_font = pygame.font.Font(None, 80)
button_font = pygame.font.Font(None, 50)
button_font_small = pygame.font.Font(None, 30) # ★ リトライボタン用の小さいフォント

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
# ★ 手の開閉状態を追跡 (初期値は開いていると仮定)
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
# ★ スタートボタンをゲームパネル中央に配置 (スクリーン座標基準)
start_button_rect_screen = pygame.Rect(0, 0, 200, 80)
start_button_rect_screen.center = (GAME_PANEL_RECT.centerx, GAME_PANEL_RECT.centery)
# ★ リトライボタン (スクリーン座標基準)
retry_button_rect_screen = pygame.Rect(0, 0, 300, 60) # 幅を広げる
retry_button_rect_screen.center = (GAME_PANEL_RECT.centerx, GAME_PANEL_RECT.bottom - 80)

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

# ★ ゲームリセット関数
def reset_game():
    global game_state, elapsed_time, final_time, drop_delay_ms, icicle, start_time, left_is_open_current, right_is_open_current, left_was_open, right_was_open
    game_state = 'READY'
    elapsed_time = 0
    final_time = 0
    drop_delay_ms = 0
    if icicle:
        icicle.reset()
    start_time = 0
    left_is_open_current = True # リセット時は開いていると仮定
    right_is_open_current = True
    left_was_open = True
    right_was_open = True
    global cap
    # ★ カメラが閉じていたら再度開く
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
    mouse_click = False # ★ マウスイベント用にリセット

    # 1. イベント処理
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN: # Enterキーで終了
                running = False
        # ★ マウスクリックイベントを検出
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1: # 左クリック
                mouse_click = True

    # 画面全体をクリア
    screen.fill(GRAY)

    # --- カメラ処理 & 手の検出 (常に実行) ---
    left_closed_this_frame = False # フレームごとにリセット
    right_closed_this_frame = False
    results = None # 手の検出結果初期化
    hand_detected = False # 手が検出されたかフラグ

    if cap.isOpened():
        success, image_cam = cap.read()
        if success:
            image_rgb = cv2.cvtColor(cv2.flip(image_cam, 1), cv2.COLOR_BGR2RGB)
            image_rgb.flags.writeable = False
            results = hands.process(image_rgb)
            image_rgb.flags.writeable = True

            image_bgr = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
            if results and results.multi_hand_landmarks:
                hand_detected = True # 手が検出された
                for hand_landmarks in results.multi_hand_landmarks:
                    mp_drawing.draw_landmarks(image_bgr, hand_landmarks, mp_hands.HAND_CONNECTIONS)

            image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
            image_pygame = pygame.image.frombuffer(image_rgb.tobytes(), image_rgb.shape[1::-1], "RGB")
            camera_surface_scaled = pygame.transform.scale(image_pygame, (CAM_PANEL_RECT.width, CAM_PANEL_RECT.height))

            # --- ジェスチャー & カーソル位置更新 ---
            left_is_open_now = True
            right_is_open_now = True
            left_cursor_pos[:] = [-100, -100]
            right_cursor_pos[:] = [-100, -100]

            if results and results.multi_hand_landmarks:
                for hand_landmarks, handedness in zip(results.multi_hand_landmarks, results.multi_handedness):
                    is_open = is_hand_open(hand_landmarks)
                    mcp_landmark = hand_landmarks.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_MCP]
                    # ★ 座標はゲームパネル基準
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

        else: # cap.read()失敗
             if cap.isOpened():
                 print("Warning: Failed to read frame from camera.")
             # 状態は維持するが、位置はリセット
             left_cursor_pos[:] = [-100, -100]
             right_cursor_pos[:] = [-100, -100]

    else: # cap is not Opened
        # 状態はデフォルト（開）、位置はリセット
        left_is_open_current = True
        right_is_open_current = True
        left_cursor_pos[:] = [-100, -100]
        right_cursor_pos[:] = [-100, -100]


    # --- ゲームロジック (状態に基づいて実行) ---

    # ★ 座標系を統一するため、ゲームパネル基準のRectを作成
    left_cursor_rect_game = pygame.Rect(left_cursor_pos[0] - cursor_radius, left_cursor_pos[1] - cursor_radius, cursor_radius * 2, cursor_radius * 2)
    right_cursor_rect_game = pygame.Rect(right_cursor_pos[0] - cursor_radius, right_cursor_pos[1] - cursor_radius, cursor_radius * 2, cursor_radius * 2)
    start_button_rect_game = start_button_rect_screen.copy()
    start_button_rect_game.center = (start_button_rect_screen.centerx - GAME_PANEL_RECT.left, start_button_rect_screen.centery - GAME_PANEL_RECT.top)
    retry_button_rect_game = retry_button_rect_screen.copy()
    retry_button_rect_game.center = (retry_button_rect_screen.centerx - GAME_PANEL_RECT.left, retry_button_rect_screen.centery - GAME_PANEL_RECT.top)


    if game_state == 'READY':
        start_activated = False
        # ★ 修正: ゲームパネル基準の座標で衝突判定
        if left_closed_this_frame and start_button_rect_game.colliderect(left_cursor_rect_game):
            start_activated = True
        elif right_closed_this_frame and start_button_rect_game.colliderect(right_cursor_rect_game):
            start_activated = True

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
            icicle.update(GRAVITY_ACCEL)
            if icicle.rect.top > GAME_HEIGHT:
                game_state = 'MISSED'
                final_time = elapsed_time
                if cap.isOpened():
                    cap.release()
                    print("Camera released on game over.")

            icicle_rect_game = icicle.rect

            caught = False
             # ★ 修正: ゲームパネル基準の座標で衝突判定
            if left_closed_this_frame and left_cursor_rect_game.colliderect(icicle_rect_game):
                caught = True
            elif right_closed_this_frame and right_cursor_rect_game.colliderect(icicle_rect_game):
                caught = True

            if caught:
                game_state = 'CAUGHT'
                final_time = elapsed_time
                if cap.isOpened():
                    cap.release()
                    print("Camera released on success.")

    elif game_state == 'CAUGHT' or game_state == 'MISSED':
        # ★ マウスクリックでリトライ
        mouse_x_in_game = mouse_pos[0] - GAME_PANEL_RECT.left
        mouse_y_in_game = mouse_pos[1] - GAME_PANEL_RECT.top

        if GAME_PANEL_RECT.collidepoint(mouse_pos):
             # ★ 修正: ゲームパネル基準の座標で衝突判定
             if retry_button_rect_game.collidepoint(mouse_x_in_game, mouse_y_in_game) and mouse_click:
                  reset_game()


    # --- 描画処理 ---

    # --- ゲームパネル (右側) ---
    game_surface = screen.subsurface(GAME_PANEL_RECT)
    game_surface.fill(SKY_BLUE)

    if game_state == 'CAUGHT':
        # --- 成功画面描画 ---
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

        # リトライボタン描画 (マウスホバー)
        mouse_x_in_game = mouse_pos[0] - GAME_PANEL_RECT.left
        mouse_y_in_game = mouse_pos[1] - GAME_PANEL_RECT.top
        # ★ 修正: ゲームパネル基準の座標で衝突判定
        is_hovering_retry = retry_button_rect_game.collidepoint(mouse_x_in_game, mouse_y_in_game)

        btn_color = BUTTON_HOVER_COLOR if is_hovering_retry else BUTTON_COLOR
        # ★ 修正: ゲームパネル基準の座標で描画
        pygame.draw.rect(game_surface, btn_color, retry_button_rect_game, border_radius=10)
        btn_text = button_font_small.render("Retry Challenge", True, BUTTON_TEXT_COLOR)
        # ★ 修正: ゲームパネル基準の座標で描画
        game_surface.blit(btn_text, btn_text.get_rect(center=retry_button_rect_game.center))

    elif game_state == 'MISSED':
        # --- ゲームオーバー画面描画 ---
        go_text = game_over_font.render("GAME OVER", True, RED)
        game_surface.blit(go_text, go_text.get_rect(center=(GAME_PANEL_WIDTH // 2, GAME_HEIGHT // 2 - 50)))
        time_text = font_ui.render(f"Final Time: {format_time(final_time)}", True, WHITE) # Game Over時は白文字
        game_surface.blit(time_text, time_text.get_rect(center=(GAME_PANEL_WIDTH // 2, GAME_HEIGHT // 2 + 50)))

        # リトライボタン描画 (マウスホバー)
        mouse_x_in_game = mouse_pos[0] - GAME_PANEL_RECT.left
        mouse_y_in_game = mouse_pos[1] - GAME_PANEL_RECT.top
        # ★ 修正: ゲームパネル基準の座標で衝突判定
        is_hovering_retry = retry_button_rect_game.collidepoint(mouse_x_in_game, mouse_y_in_game)

        btn_color = BUTTON_HOVER_COLOR if is_hovering_retry else BUTTON_COLOR
        # ★ 修正: ゲームパネル基準の座標で描画
        pygame.draw.rect(game_surface, btn_color, retry_button_rect_game, border_radius=10)
        btn_text = button_font_small.render("Retry Challenge", True, BUTTON_TEXT_COLOR)
        # ★ 修正: ゲームパネル基準の座標で描画
        game_surface.blit(btn_text, btn_text.get_rect(center=retry_button_rect_game.center))

    else: # READY, WAITING, DROPPING
        # --- ゲーム実行中描画 ---
        if icicle and (game_state == 'WAITING' or game_state == 'DROPPING'):
             icicle.draw(game_surface)

        if game_state == 'READY':
            # ★ スタートボタンのホバー判定も手のカーソル (ゲームパネル基準)
            is_hovering_start = start_button_rect_game.colliderect(left_cursor_rect_game) or start_button_rect_game.colliderect(right_cursor_rect_game)
            btn_color = BUTTON_HOVER_COLOR if is_hovering_start else BUTTON_COLOR
            # ★ 修正: ゲームパネル基準の座標で描画
            pygame.draw.rect(game_surface, btn_color, start_button_rect_game, border_radius=10)
            btn_text = button_font.render("START", True, BUTTON_TEXT_COLOR)
            # ★ 修正: ゲームパネル基準の座標で描画
            game_surface.blit(btn_text, btn_text.get_rect(center=start_button_rect_game.center))

        # カーソル描画 (常に表示, ゲームパネル基準)
        left_cursor_color = GREEN if not left_is_open_current else RED # 閉じていたら緑
        right_cursor_color = GREEN if not right_is_open_current else RED # 閉じていたら緑
        ALPHA_VALUE = 128

        if left_cursor_pos[0] != -100:
            circle_surface_left = pygame.Surface((cursor_radius * 2, cursor_radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(circle_surface_left, left_cursor_color + (ALPHA_VALUE,), (cursor_radius, cursor_radius), cursor_radius)
            game_surface.blit(circle_surface_left, left_cursor_rect_game.topleft) # ★ topleftで指定

        if right_cursor_pos[0] != -100:
            circle_surface_right = pygame.Surface((cursor_radius * 2, cursor_radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(circle_surface_right, right_cursor_color + (ALPHA_VALUE,), (cursor_radius, cursor_radius), cursor_radius)
            game_surface.blit(circle_surface_right, right_cursor_rect_game.topleft) # ★ topleftで指定


    # --- UIパネルの描画 (常に実行) ---

    # --- スコアパネル (左上) ---
    score_surface = screen.subsurface(SCORE_PANEL_RECT)
    score_surface.fill(BLACK)
    title_text = font_title.render("TIMER", True, WHITE)
    score_surface.blit(title_text, (10, 10))

    display_time = elapsed_time if final_time == 0 else final_time
    time_text = font_ui.render(f"{format_time(display_time)}", True, WHITE)
    score_surface.blit(time_text, (15, 60))

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
         # ★ ゲーム終了状態でもエラー表示しない
         if game_state not in ['CAUGHT', 'MISSED']:
             cam_error_text = font_log.render("Camera not found.", True, RED)
             cam_surface.blit(cam_error_text, (10, 50))

    # 画面更新
    pygame.display.flip()

# --- 終了処理 ---
if cap.isOpened():
    cap.release()
cv2.destroyAllWindows()
pygame.quit()
sys.exit()

