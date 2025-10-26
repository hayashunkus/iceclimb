import cv2
import mediapipe as mp
import pygame
import math
import random
import numpy as np # カメラ映像変換に必要

# --- 初期設定 ---

# MediaPipeの手検出モデルと描画ツールを準備
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
hands = mp_hands.Hands(
    max_num_hands=2,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.7
)

# Pygameの初期化
pygame.init()
pygame.font.init() # フォントモジュールを明示的に初期化

# --- ★ 画面レイアウト定義 ---
SCREEN_WIDTH, SCREEN_HEIGHT = 1280, 720
LEFT_PANEL_WIDTH = int(SCREEN_WIDTH * 0.2) # 256
GAME_PANEL_WIDTH = SCREEN_WIDTH - LEFT_PANEL_WIDTH # 1024
GAME_HEIGHT = SCREEN_HEIGHT # 720

# 各パネルのRectを定義
SCORE_PANEL_RECT = pygame.Rect(0, 0, LEFT_PANEL_WIDTH, int(SCREEN_HEIGHT * 0.4))
LOG_PANEL_RECT = pygame.Rect(0, SCORE_PANEL_RECT.height, LEFT_PANEL_WIDTH, int(SCREEN_HEIGHT * 0.3))
CAM_PANEL_RECT = pygame.Rect(0, SCORE_PANEL_RECT.height + LOG_PANEL_RECT.height, LEFT_PANEL_WIDTH, int(SCREEN_HEIGHT * 0.3))
GAME_PANEL_RECT = pygame.Rect(LEFT_PANEL_WIDTH, 0, GAME_PANEL_WIDTH, GAME_HEIGHT)

# --- ★エネミーの定義 ---
class Enemy(pygame.sprite.Sprite):
    def __init__(self, image, speed=2): # ★ 基本速度を 2 に変更
        super().__init__()
        self.image = image
        self.rect = self.image.get_rect()
        # ★ 座標をゲームパネル(1024px)基準に変更
        self.rect.x = random.randint(0, GAME_PANEL_WIDTH - self.rect.width)
        self.rect.y = -self.rect.height 
        self.speed = speed

    def update(self):
        # 画面下に向かって移動
        self.rect.y += self.speed
        # ★ プレイヤーの登頂速度による相対的な速度変化は、
        # ★ メインループの world_y_offset 描画で自動的に処理されます

    def draw(self, surface):
        surface.blit(self.image, self.rect)


# --- ゲーム設定と物理定義 ---
PIXELS_PER_METER = 360  
TOTAL_CLIMB_METERS = 105.0 
MAX_PULL_METERS = 2.0
GOAL_THRESHOLD_METERS = 100.0 # ★ 100mでクリア
GOAL_ZONE_METERS = 5.0 # 最後の5mはホールド無し (100mまで生成)

TOTAL_CLIMB_PIXELS = int(TOTAL_CLIMB_METERS * PIXELS_PER_METER)
MAX_PULL_PIXELS = int(MAX_PULL_METERS * PIXELS_PER_METER)

# ★ 物理演算の変更 (自由落下)
GRAVITY_ACCEL = 0.8  # ★ 重力加速度
current_fall_velocity = 0.0 # ★ 現在の落下速度
MAX_FALL_SPEED = 30 # ★ 最大落下速度

# Pygameウィンドウの設定
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption(f"Bouldering Game ({int(TOTAL_CLIMB_METERS-5)}m Climb)") # 100m Climb

# 色とフォントの定義
WHITE = (255, 255, 255)
RED = (255, 0, 0)
GREEN = (0, 255, 0) 
BLACK = (0, 0, 0)
GRAY = (50, 50, 50) # パネル背景色
SKY_BLUE = (135, 206, 235)
BLUE = (0, 0, 255) 

# ★ フォントを複数サイズ定義
font_ui = pygame.font.Font(None, 36) # UI用
font_log = pygame.font.Font(None, 24) # ログ用
font_title = pygame.font.Font(None, 40) # パネルタイトル用
game_over_font = pygame.font.Font(None, 100) 
goal_text_font = pygame.font.Font(None, 80) # 登頂テキスト用

# ★エネミーの画像読み込み
enemy_image = None
try:
    enemy_image = pygame.image.load("image/enemy.png").convert_alpha() 
except FileNotFoundError:
    print("エラー: image/enemy.png が見つかりません。")

# ★ ゴール背景の読み込み
goal_background_image = None
try:
    img = pygame.image.load("image/goaliceclimb.png").convert()
    # ★ 画面サイズをゲームパネル(1024x720)に合わせる
    goal_background_image = pygame.transform.scale(img, (GAME_PANEL_WIDTH, GAME_HEIGHT))
except FileNotFoundError:
    print("エラー: image/goaliceclimb.png が見つかりません。")

# ★ ダンサーアニメーション画像の読み込み
dancer_images = []
dancer_frame = 0
dancer_frame_time = 0
ANIMATION_SPEED_MS = 100 
try:
    for i in range(1, 6):
        img_path = f"image/c-dancer-{i}.png"
        img = pygame.image.load(img_path).convert_alpha()
        img = pygame.transform.scale(img, (300, 300)) # リサイズ
        dancer_images.append(img)
except FileNotFoundError as e:
    print(f"エラー: ダンサー画像が見つかりません。 {e}")


# ★エネミー管理リスト
enemy_list = [] 

# ★エネミー出現イベント
ENEMY_SPAWN_EVENT = pygame.USEREVENT + 1
pygame.time.set_timer(ENEMY_SPAWN_EVENT, 5000)

# プレイヤー（カーソル）の設定 (左右別々に)
left_cursor_pos = [-100, -100]
right_cursor_pos = [-100, -100]
cursor_radius = 45 

# ★デコピン（Flick）検知用の変数
FLICK_THRESHOLD = 40
left_middle_tip_y = [0, 0]
right_middle_tip_y = [0, 0]
left_flick_pos = [-100, -100]
right_flick_pos = [-100, -100]
left_flick_detected = False
right_flick_detected = False


# Webカメラの準備
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("エラー: カメラを起動できません。")
    running = False

# --- 100mの壁を生成 ---
full_background = None
try:
    tile_image = pygame.image.load("image/backsnow.png").convert()
    tile_height = tile_image.get_height()
    # ★ 壁の幅をゲームパネル(1024px)に合わせる
    full_background = pygame.Surface((GAME_PANEL_WIDTH, TOTAL_CLIMB_PIXELS))
    for y in range(0, TOTAL_CLIMB_PIXELS, tile_height):
        full_background.blit(tile_image, (0, y))
except FileNotFoundError:
    print("エラー: image/backsnow.png が見つかりません。")

# 背景スクロール用の変数
if full_background:
    max_scroll = full_background.get_height() - GAME_HEIGHT
    world_y_offset = max_scroll # スタート時は一番下
else:
    max_scroll = 0
    world_y_offset = 0

# --- ホールド（掴む岩）の生成 ---
holds_list = [] 
hold_image = None
try:
    hold_image = pygame.image.load("image/blockcatch.png").convert_alpha()
    hold_rect = hold_image.get_rect()
    hold_width, hold_height = hold_rect.width, hold_rect.height
    
    GOAL_ZONE_PIXELS = GOAL_ZONE_METERS * PIXELS_PER_METER 

    current_y = TOTAL_CLIMB_PIXELS - (GAME_HEIGHT // 2)
    side = 0 
    
    while current_y > GOAL_ZONE_PIXELS: 
        y_variation = random.randint(-PIXELS_PER_METER // 4, PIXELS_PER_METER // 4)
        h_y = current_y + y_variation
        if h_y < GOAL_ZONE_PIXELS:
             h_y = GOAL_ZONE_PIXELS + random.randint(10, 50)

        x_variation = random.randint(-80, 80)
        # ★ 座標をゲームパネル(1024px)基準に変更
        if side == 0:
            h_x = (GAME_PANEL_WIDTH / 4) - (hold_width / 2) + x_variation
        else:
            h_x = (GAME_PANEL_WIDTH * 3 / 4) - (hold_width / 2) + x_variation
        
        holds_list.append(pygame.Rect(h_x, h_y, hold_width, hold_height))
        current_y -= PIXELS_PER_METER
        side = 1 - side 
except FileNotFoundError:
    print("エラー: image/blockcatch.png が見つかりません。")

# --- 掴み状態の管理変数 (左右別々に) ---
left_was_holding = False
right_was_holding = False
left_hold_start_y = 0
right_hold_start_y = 0
world_hold_start_y = 0

# --- ★ゲーム状態の管理 ---
game_over = False
game_won = False 
is_near_goal = False

# --- ★タイマー変数 ---
start_time = 0
elapsed_time = 0
final_time = 0
game_start_flag = False # 最初の動きでタイマースタート

# --- ★テキストログ変数 ---
log_messages = []
MAX_LOG_LINES = 6
enemy_kill_count = 0

# --- ★ 関数定義 ---

def is_hand_open(hand_landmarks):
    tip_ids = [mp_hands.HandLandmark.INDEX_FINGER_TIP, mp_hands.HandLandmark.MIDDLE_FINGER_TIP, mp_hands.HandLandmark.RING_FINGER_TIP, mp_hands.HandLandmark.PINKY_TIP]
    pip_ids = [mp_hands.HandLandmark.INDEX_FINGER_PIP, mp_hands.HandLandmark.MIDDLE_FINGER_PIP, mp_hands.HandLandmark.RING_FINGER_PIP, mp_hands.HandLandmark.PINKY_PIP]
    open_fingers = sum(1 for tip_id, pip_id in zip(tip_ids, pip_ids) if hand_landmarks.landmark[tip_id].y < hand_landmarks.landmark[pip_id].y)
    return open_fingers >= 3

# ★ テキストログ追加関数
def add_log(message):
    log_messages.append(message)
    if len(log_messages) > MAX_LOG_LINES:
        log_messages.pop(0) # 古いログを削除

# ★ タイムフォーマット関数 (ms -> MM:SS.ss)
def format_time(ms):
    total_seconds = ms // 1000
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    milliseconds = (ms % 1000) // 10 # 2桁
    return f"{minutes:02}:{seconds:02}.{milliseconds:02}"

# --- メインループ ---
running = True
clock = pygame.time.Clock()
add_log("Game Ready. Press 'R' for 90m Rocket.")

while running:
    
    # 1. イベント処理 (常に実行)
    if 'max_scroll' in locals():
        height_climbed = (max_scroll - world_y_offset) / PIXELS_PER_METER
        is_near_goal = height_climbed >= GOAL_THRESHOLD_METERS # 100m地点の判定
    else:
        height_climbed = 0
        is_near_goal = False

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                running = False
            
            if event.key == pygame.K_r and not game_over and not game_won: # ★ 'R'キーでロケット
                warp_height_meters = 90.0
                current_max_scroll = (int(TOTAL_CLIMB_METERS * PIXELS_PER_METER)) - GAME_HEIGHT
                
                warp_y_offset = current_max_scroll - (warp_height_meters * PIXELS_PER_METER)
                
                if warp_y_offset < 0: warp_y_offset = 0
                if warp_y_offset > current_max_scroll: warp_y_offset = current_max_scroll
                
                world_y_offset = warp_y_offset
                left_was_holding = False
                right_was_holding = False
                current_fall_velocity = 0 # 落下速度リセット
                add_log("ROCKET! Warping to 90m.")

        
        if event.type == ENEMY_SPAWN_EVENT and not game_over and not game_won and not is_near_goal:
            if enemy_image: 
                enemy_list.append(Enemy(enemy_image))

    # ★ 画面全体を一度クリア
    screen.fill(GRAY) # パネルの隙間・背景色

    # ★ ゲーム状態によって処理を分岐 ★
    if game_won:
        # --- ★★★ GAME CLEAR ★★★ ---
        
        if final_time == 0: # 最終タイムを一度だけ記録
            final_time = elapsed_time
            add_log(f"GOAL! Time: {format_time(final_time)}")
        
        # ★ ゲームパネルサーフェスを取得
        game_surface = screen.subsurface(GAME_PANEL_RECT)

        # ゴール背景を描画
        if goal_background_image:
            game_surface.blit(goal_background_image, (0, 0))
        else:
            game_surface.fill(SKY_BLUE) 

        # ★ 登頂おめでとうテキスト
        goal_text = goal_text_font.render("100m Climb Success!!", True, WHITE)
        game_surface.blit(goal_text, (
            game_surface.get_width() // 2 - goal_text.get_width() // 2,
            game_surface.get_height() // 4 - goal_text.get_height() // 2
        ))
        
        # ★ 最終タイム表示
        time_text = font_ui.render(f"Clear Time: {format_time(final_time)}", True, WHITE)
        game_surface.blit(time_text, (
            game_surface.get_width() // 2 - time_text.get_width() // 2,
            game_surface.get_height() // 4 + goal_text.get_height()
        ))


        # ダンサーアニメーション
        if dancer_images:
            dancer_frame_time += clock.get_time()
            if dancer_frame_time > ANIMATION_SPEED_MS:
                dancer_frame = (dancer_frame + 1) % len(dancer_images)
                dancer_frame_time = 0
            
            current_dancer_image = dancer_images[dancer_frame]
            img_rect = current_dancer_image.get_rect(center=(game_surface.get_width() // 2, game_surface.get_height() // 2 + 100))
            game_surface.blit(current_dancer_image, img_rect)
        
        # ★ カメラを閉じる (Pygameウィンドウだけが残る)
        if cap.isOpened():
            cap.release()
            cv2.destroyAllWindows()

    elif not game_over:
        # --- ★★★ GAME RUNNING ★★★ ---

        if is_near_goal: # 100m到達
            game_won = True
            pygame.display.flip() 
            continue 

        if not cap.isOpened():
            add_log("Camera feed lost.")
            break

        success, image_cam = cap.read()
        if not success: continue

        # 2. 手の検出
        image_rgb = cv2.cvtColor(cv2.flip(image_cam, 1), cv2.COLOR_BGR2RGB)
        image_rgb.flags.writeable = False
        results = hands.process(image_rgb)

        # 3. ★ カメラ映像の描画 (左下パネルへ)
        image_bgr = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR) # 描画用にBGRに戻す
        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                mp_drawing.draw_landmarks(image_bgr, hand_landmarks, mp_hands.HAND_CONNECTIONS)
        
        # ★ OpenCV(BGR) -> Pygame(RGB) 変換
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB) # Pygame用にRGB
        image_pygame = pygame.image.frombuffer(image_rgb.tobytes(), image_rgb.shape[1::-1], "RGB")
        image_scaled = pygame.transform.scale(image_pygame, (CAM_PANEL_RECT.width, CAM_PANEL_RECT.height))
        
        cam_surface = screen.subsurface(CAM_PANEL_RECT)
        cam_surface.blit(image_scaled, (0, 0))

        # ★ cv2.imshow() を削除

        # 4. ジェスチャーとゲームロジック (左右分離)
        
        left_is_grabbing = False
        right_is_grabbing = False
        left_flick_detected = False 
        right_flick_detected = False 
        
        left_cursor_pos[:] = [-100, -100]  
        right_cursor_pos[:] = [-100, -100] 
        left_flick_pos[:] = [-100, -100] 
        right_flick_pos[:] = [-100, -100] 
        
        if results.multi_hand_landmarks:
            for hand_landmarks, handedness in zip(results.multi_hand_landmarks, results.multi_handedness):
                
                is_open = is_hand_open(hand_landmarks)
                mcp_landmark = hand_landmarks.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_MCP]
                
                # ★ 座標をゲームパネル(1024px)基準に変更
                hand_pos = (int(mcp_landmark.x * GAME_PANEL_WIDTH), int(mcp_landmark.y * GAME_HEIGHT))
                
                middle_tip = hand_landmarks.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_TIP]
                # ★ 座標をゲームパネル(1024px)基準に変更
                flick_pos_x = int(middle_tip.x * GAME_PANEL_WIDTH)
                flick_pos_y = int(middle_tip.y * GAME_HEIGHT)

                if handedness.classification[0].label == 'Left':
                    left_is_grabbing = not is_open
                    left_cursor_pos[:] = hand_pos
                    left_flick_pos[:] = (flick_pos_x, flick_pos_y) 
                    
                    left_middle_tip_y[0] = left_middle_tip_y[1] 
                    left_middle_tip_y[1] = flick_pos_y         
                    flick_velocity = left_middle_tip_y[0] - left_middle_tip_y[1] 
                    
                    if is_open and flick_velocity > FLICK_THRESHOLD:
                        left_flick_detected = True

                elif handedness.classification[0].label == 'Right':
                    right_is_grabbing = not is_open
                    right_cursor_pos[:] = hand_pos
                    right_flick_pos[:] = (flick_pos_x, flick_pos_y) 

                    right_middle_tip_y[0] = right_middle_tip_y[1]
                    right_middle_tip_y[1] = flick_pos_y
                    flick_velocity = right_middle_tip_y[0] - right_middle_tip_y[1]

                    if is_open and flick_velocity > FLICK_THRESHOLD:
                        right_flick_detected = True

        # --- 当たり判定 (ホールド) ---
        left_cursor_rect = pygame.Rect(left_cursor_pos[0] - cursor_radius, left_cursor_pos[1] - cursor_radius, cursor_radius * 2, cursor_radius * 2)
        right_cursor_rect = pygame.Rect(right_cursor_pos[0] - cursor_radius, right_cursor_pos[1] - cursor_radius, cursor_radius * 2, cursor_radius * 2)
        
        visible_holds_for_drawing = []
        left_colliding_hold = None
        right_colliding_hold = None
        
        if hold_image:
            min_y_world = world_y_offset
            max_y_world = world_y_offset + GAME_HEIGHT
            for hold_rect_world in holds_list:
                if hold_rect_world.bottom > min_y_world and hold_rect_world.top < max_y_world:
                    screen_rect = hold_rect_world.move(0, -world_y_offset)
                    visible_holds_for_drawing.append(screen_rect) 
                    
                    if left_colliding_hold is None and left_cursor_rect.colliderect(screen_rect):
                        left_colliding_hold = screen_rect
                    if right_colliding_hold is None and right_cursor_rect.colliderect(screen_rect):
                        right_colliding_hold = screen_rect

        # --- ★★★ 掴みとスクロールのロジック ★★★ ---
        left_can_grab = left_is_grabbing and (left_colliding_hold is not None)
        right_can_grab = right_is_grabbing and (right_colliding_hold is not None)
        
        # ★ タイマースタート処理
        if not game_start_flag and (left_can_grab or right_can_grab):
            game_start_flag = True
            start_time = pygame.time.get_ticks()
            add_log("Climb START!")

        left_grabbed_this_frame = left_can_grab and not left_was_holding
        right_grabbed_this_frame = right_can_grab and not right_was_holding

        if left_grabbed_this_frame or right_grabbed_this_frame: 
            world_hold_start_y = world_y_offset
            if left_can_grab:
                left_hold_start_y = left_cursor_pos[1]
            if right_can_grab:
                right_hold_start_y = right_cursor_pos[1]

        if left_can_grab or right_can_grab:
            current_fall_velocity = 0 # ★ 掴んだら落下速度リセット
            pull_distance_left = 0
            pull_distance_right = 0
            if left_can_grab:
                pull_distance_left = left_cursor_pos[1] - left_hold_start_y
            if right_can_grab:
                pull_distance_right = right_cursor_pos[1] - right_hold_start_y
            
            pull_distance = max(pull_distance_left, pull_distance_right)
            
            if pull_distance < 0: pull_distance = 0
            if pull_distance > MAX_PULL_PIXELS: pull_distance = MAX_PULL_PIXELS
            
            world_y_offset = world_hold_start_y - pull_distance

        else: # どちらの手も掴んでいない
            # ★ 自由落下
            current_fall_velocity += GRAVITY_ACCEL
            if current_fall_velocity > MAX_FALL_SPEED:
                current_fall_velocity = MAX_FALL_SPEED
            world_y_offset += int(current_fall_velocity)
        
        left_was_holding = left_can_grab
        right_was_holding = right_can_grab
        
        if world_y_offset > max_scroll: world_y_offset = max_scroll
        if world_y_offset <= 0: # 103m以上に到達
            world_y_offset = 0
            # is_near_goal が 100m, 103mでも game_won にする
            is_near_goal = True # 念のため
            game_won = True
        
        # --- ★エネミーの更新と当たり判定 ---
        if not is_near_goal: # 100m未満の場合のみ
            left_flick_rect = pygame.Rect(left_flick_pos[0] - cursor_radius, left_flick_pos[1] - cursor_radius, cursor_radius*2, cursor_radius*2)
            right_flick_rect = pygame.Rect(right_flick_pos[0] - cursor_radius, right_flick_pos[1] - cursor_radius, cursor_radius*2, cursor_radius*2)

            for enemy in enemy_list[:]:
                enemy.update()
                
                # ★ ゲームパネルの高さで判定
                if enemy.rect.top > GAME_HEIGHT:
                    enemy_list.remove(enemy) 
                    game_over = True         
                    break 
                
                # ★ キルボーナス処理
                killed = False
                if left_flick_detected and left_flick_rect.colliderect(enemy.rect):
                    enemy_list.remove(enemy)
                    killed = True
                
                elif right_flick_detected and right_flick_rect.colliderect(enemy.rect):
                    enemy_list.remove(enemy)
                    killed = True
                
                if killed:
                    enemy_kill_count += 1
                    add_log(f"Enemy Defeated! ({enemy_kill_count})")
                    if enemy_kill_count > 0 and enemy_kill_count % 5 == 0:
                        add_log("5 Kills! +10m Bonus!")
                        world_y_offset -= (10 * PIXELS_PER_METER)
                        if world_y_offset < 0: world_y_offset = 0
                        # 掴み状態をリセットしないと、基準点がおかしくなって落下する
                        left_was_holding = False
                        right_was_holding = False
                        current_fall_velocity = 0


        if game_over: 
            if final_time == 0:
                final_time = elapsed_time
                add_log(f"GAME OVER... Time: {format_time(final_time)}")
            pass 

        # 5. Pygameの描画処理
        
        # ★ ゲームパネルサーフェスを取得
        game_surface = screen.subsurface(GAME_PANEL_RECT)

        # 背景の描画
        if full_background:
            game_surface.blit(full_background, (0, -world_y_offset))
        else:
            game_surface.fill(SKY_BLUE)
        
        # ホールドとエネミーの描画
        if hold_image:
            for rect in visible_holds_for_drawing:
                game_surface.blit(hold_image, rect)
        
        for enemy in enemy_list:
            enemy.draw(game_surface) # game_surfaceに描画

        # 左右の（掴み用）カーソルを描画
        left_cursor_color = GREEN if left_can_grab else RED
        right_cursor_color = GREEN if right_can_grab else RED
        ALPHA_VALUE = 128 

        if left_cursor_pos[0] != -100: 
            circle_surface_left = pygame.Surface((cursor_radius * 2, cursor_radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(circle_surface_left, left_cursor_color + (ALPHA_VALUE,), (cursor_radius, cursor_radius), cursor_radius)
            game_surface.blit(circle_surface_left, (left_cursor_pos[0] - cursor_radius, left_cursor_pos[1] - cursor_radius))

        if right_cursor_pos[0] != -100: 
            circle_surface_right = pygame.Surface((cursor_radius * 2, cursor_radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(circle_surface_right, right_cursor_color + (ALPHA_VALUE,), (cursor_radius, cursor_radius), cursor_radius)
            game_surface.blit(circle_surface_right, (right_cursor_pos[0] - cursor_radius, right_cursor_pos[1] - cursor_radius))

        # ★デコピンのエフェクトを描画
        if left_flick_detected:
            pygame.draw.circle(game_surface, BLUE, left_flick_pos, cursor_radius + 10, 5) 
        if right_flick_detected:
            pygame.draw.circle(game_surface, BLUE, right_flick_pos, cursor_radius + 10, 5)

    else:
        # --- ★★★ GAME OVER ★★★ ---
        if final_time == 0: # 最終タイムを一度だけ記録
            final_time = elapsed_time
            add_log(f"GAME OVER... Time: {format_time(final_time)}")

        # ★ ゲームパネルサーフェスを取得
        game_surface = screen.subsurface(GAME_PANEL_RECT)
        game_surface.fill(BLACK)
        go_text = game_over_font.render("GAME OVER", True, RED)
        game_surface.blit(go_text, (
            game_surface.get_width() // 2 - go_text.get_width() // 2,
            game_surface.get_height() // 2 - go_text.get_height() // 2 - 50
        ))

        # ★ 最終タイム表示
        time_text = font_ui.render(f"Final Time: {format_time(final_time)}", True, WHITE)
        game_surface.blit(time_text, (
            game_surface.get_width() // 2 - time_text.get_width() // 2,
            game_surface.get_height() // 2 + 50
        ))
        
        # ★ カメラを閉じる
        if cap.isOpened():
            cap.release()
            cv2.destroyAllWindows()

    # --- ★★★ UIパネルの描画 (全状態共通) ★★★ ---
    
    # ★ タイム更新
    if game_start_flag and not game_won and not game_over:
        elapsed_time = pygame.time.get_ticks() - start_time
    
    # --- スコアパネル (左上) ---
    score_surface = screen.subsurface(SCORE_PANEL_RECT)
    score_surface.fill(BLACK)
    # タイトル
    title_text = font_title.render("SCORE", True, WHITE)
    score_surface.blit(title_text, (10, 10))
    # 高さ
    height_text_str = f"Height: {height_climbed:.1f} m"
    height_text = font_ui.render(height_text_str, True, WHITE)
    score_surface.blit(height_text, (15, 60))
    # タイム
    time_text_str = f"Time: {format_time(elapsed_time)}"
    if final_time > 0:
        time_text_str = f"Time: {format_time(final_time)}"
    time_text = font_ui.render(time_text_str, True, WHITE)
    score_surface.blit(time_text, (15, 110))
    # キル数
    kill_text_str = f"Kills: {enemy_kill_count}"
    kill_text = font_ui.render(kill_text_str, True, WHITE)
    score_surface.blit(kill_text, (15, 160))
    # Rキー
    r_text = font_log.render("'R' Key: 90m Rocket", True, GREEN)
    score_surface.blit(r_text, (15, 250))


    # --- ログパネル (左中) ---
    log_surface = screen.subsurface(LOG_PANEL_RECT)
    log_surface.fill(BLACK)
    # タイトル
    log_title = font_title.render("LOG", True, WHITE)
    log_surface.blit(log_title, (10, 10))
    # ログメッセージ
    y_pos = 50
    for message in log_messages:
        log_text = font_log.render(message, True, GREEN)
        log_surface.blit(log_text, (15, y_pos))
        y_pos += 25

    # --- カメラパネル (左下) ---
    if not cap.isOpened() and not game_won and not game_over:
        # カメラが落ちた場合の描画
        cam_surface = screen.subsurface(CAM_PANEL_RECT)
        cam_surface.fill(BLACK)
        cam_error_text = font_log.render("Camera not found.", True, RED)
        cam_surface.blit(cam_error_text, (10, 10))
    elif game_won or game_over:
        # ゲーム終了後はカメラパネルを黒くする
        cam_surface = screen.subsurface(CAM_PANEL_RECT)
        cam_surface.fill(BLACK)

    # 画面更新 (全状態共通)
    pygame.display.flip()
    clock.tick(60)

# --- 終了処理 ---
if cap.isOpened():
    cap.release()
cv2.destroyAllWindows()
pygame.quit()
