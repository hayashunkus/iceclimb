import cv2
import mediapipe as mp
import pygame
import math
import random

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

# --- ★エネミーの定義 ---
class Enemy(pygame.sprite.Sprite):
    def __init__(self, image, speed=5):
        super().__init__()
        self.image = image
        self.rect = self.image.get_rect()
        # 画面上部のランダムなX座標に出現
        self.rect.x = random.randint(0, SCREEN_WIDTH - self.rect.width)
        self.rect.y = -self.rect.height # 画面の上端よりさらに上
        self.speed = speed

    def update(self):
        # 画面下に向かって移動
        self.rect.y += self.speed

    def draw(self, surface):
        surface.blit(self.image, self.rect)


# --- ゲーム設定と物理定義 ---
PIXELS_PER_METER = 360  # 1メートルあたりのピクセル数
TOTAL_CLIMB_METERS = 100.0
MAX_PULL_METERS = 2.0

TOTAL_CLIMB_PIXELS = int(TOTAL_CLIMB_METERS * PIXELS_PER_METER)
MAX_PULL_PIXELS = int(MAX_PULL_METERS * PIXELS_PER_METER)
GRAVITY = 5 # 落下速度

# Pygameウィンドウの設定
SCREEN_WIDTH, SCREEN_HEIGHT = 1280, 720
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption(f"Bouldering Game ({int(TOTAL_CLIMB_METERS)}m Climb)")

# 色とフォントの定義
WHITE = (255, 255, 255)
RED = (255, 0, 0)
GREEN = (0, 255, 0) # 掴んだ時の色
BLACK = (0, 0, 0)
SKY_BLUE = (135, 206, 235)
BLUE = (0, 0, 255) # ★デコピンのエフェクト色
font = pygame.font.Font(None, 50)
game_over_font = pygame.font.Font(None, 100) # ★ゲームオーバー用フォント

# ★エネミーの画像読み込み (ウィンドウ作成後に移動済み)
enemy_image = None
try:
    enemy_image = pygame.image.load("image/enemy.png").convert_alpha() 
except FileNotFoundError:
    print("エラー: image/enemy.png が見つかりません。")

# ★エネミー管理リスト
enemy_list = [] 

# ★エネミー出現イベント (5000ms = 5秒ごと)
ENEMY_SPAWN_EVENT = pygame.USEREVENT + 1
pygame.time.set_timer(ENEMY_SPAWN_EVENT, 5000)

# プレイヤー（カーソル）の設定 (左右別々に)
# 検出前は画面外(-100, -100)に配置
left_cursor_pos = [-100, -100]
right_cursor_pos = [-100, -100]
cursor_radius = 45 # ★変更: カーソル半径を大きくする (30 -> 45)

# ★デコピン（Flick）検知用の変数
FLICK_THRESHOLD = 40 # ★デコピンと判定するY軸の速度（ピクセル/フレーム）
left_middle_tip_y = [0, 0]  # [前フレームのY, 現フレームのY]
right_middle_tip_y = [0, 0] # [前フレームのY, 現フレームのY]
left_flick_pos = [-100, -100] # ★デコピンの発生座標
right_flick_pos = [-100, -100] # ★デコピンの発生座標
left_flick_detected = False # ★デコピンが検知されたか
right_flick_detected = False # ★デコピンが検知されたか


# Webカメラの準備
cap = cv2.VideoCapture(0)

# --- 100mの壁を生成 ---
full_background = None
try:
    tile_image = pygame.image.load("image/backsnow.png").convert()
    tile_height = tile_image.get_height()
    full_background = pygame.Surface((SCREEN_WIDTH, TOTAL_CLIMB_PIXELS))
    for y in range(0, TOTAL_CLIMB_PIXELS, tile_height):
        full_background.blit(tile_image, (0, y))
except FileNotFoundError:
    print("エラー: image/backsnow.png が見つかりません。")

# 背景スクロール用の変数
if full_background:
    max_scroll = full_background.get_height() - SCREEN_HEIGHT
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
    
    current_y = TOTAL_CLIMB_PIXELS - (SCREEN_HEIGHT // 2)
    side = 0 
    
    while current_y > 0: 
        y_variation = random.randint(-PIXELS_PER_METER // 4, PIXELS_PER_METER // 4)
        h_y = current_y + y_variation
        x_variation = random.randint(-80, 80)
        if side == 0:
            h_x = (SCREEN_WIDTH / 4) - (hold_width / 2) + x_variation
        else:
            h_x = (SCREEN_WIDTH * 3 / 4) - (hold_width / 2) + x_variation
        
        holds_list.append(pygame.Rect(h_x, h_y, hold_width, hold_height))
        current_y -= PIXELS_PER_METER
        side = 1 - side 
except FileNotFoundError:
    print("エラー: image/blockcatch.png が見つかりません。")

# --- 掴み状態の管理変数 (左右別々に) ---
# player_is_holding = False # どちらかの手で掴んでいるか（前フレームの状態） # ★削除
left_was_holding = False  # ★変更: 左手が前フレームで掴んでいたか
right_was_holding = False # ★変更: 右手が前フレームで掴んでいたか

left_hold_start_y = 0   # 掴み始めた時の「左手Y座標」
right_hold_start_y = 0  # 掴み始めた時の「右手Y座標」
world_hold_start_y = 0  # 掴み始めた時の「背景Y座標」

# --- ★ゲーム状態の管理 ---
game_over = False # ★ゲームオーバーフラグ

# --- 関数定義 ---
def is_hand_open(hand_landmarks):
    tip_ids = [mp_hands.HandLandmark.INDEX_FINGER_TIP, mp_hands.HandLandmark.MIDDLE_FINGER_TIP, mp_hands.HandLandmark.RING_FINGER_TIP, mp_hands.HandLandmark.PINKY_TIP]
    pip_ids = [mp_hands.HandLandmark.INDEX_FINGER_PIP, mp_hands.HandLandmark.MIDDLE_FINGER_PIP, mp_hands.HandLandmark.RING_FINGER_PIP, mp_hands.HandLandmark.PINKY_PIP]
    open_fingers = sum(1 for tip_id, pip_id in zip(tip_ids, pip_ids) if hand_landmarks.landmark[tip_id].y < hand_landmarks.landmark[pip_id].y)
    return open_fingers >= 3

# --- メインループ ---
running = True
clock = pygame.time.Clock()

while running and cap.isOpened():
    # 1. イベント処理
    for event in pygame.event.get():
        if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN):
            running = False
        # ★エネミー出現イベント
        if event.type == ENEMY_SPAWN_EVENT and not game_over:
            if enemy_image: # 画像が読み込めていれば
                enemy_list.append(Enemy(enemy_image))

    success, image = cap.read()
    if not success: continue

    # 2. 手の検出
    image = cv2.cvtColor(cv2.flip(image, 1), cv2.COLOR_BGR2RGB)
    image.flags.writeable = False
    results = hands.process(image)

    # 3. カメラ映像の表示
    image.flags.writeable = True
    image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    if results.multi_hand_landmarks:
        for hand_landmarks in results.multi_hand_landmarks:
            mp_drawing.draw_landmarks(image, hand_landmarks, mp_hands.HAND_CONNECTIONS)
    cv2.imshow('MediaPipe Hands', image)
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q') or cv2.getWindowProperty('MediaPipe Hands', cv2.WND_PROP_VISIBLE) < 1:
        running = False

    # ★ゲームオーバーでない時だけゲームロジックを動かす
    if not game_over:
        # 4. ジェスチャーとゲームロジック (左右分離)
        
        # 状態をリセット
        left_is_grabbing = False
        right_is_grabbing = False
        left_flick_detected = False 
        right_flick_detected = False 
        
        left_cursor_pos[:] = [-100, -100]  # 検出されなければ画面外へ
        right_cursor_pos[:] = [-100, -100] # 検出されなければ画面外へ
        left_flick_pos[:] = [-100, -100] 
        right_flick_pos[:] = [-100, -100] 
        
        if results.multi_hand_landmarks:
            for hand_landmarks, handedness in zip(results.multi_hand_landmarks, results.multi_handedness):
                
                is_open = is_hand_open(hand_landmarks)
                # 掴み判定用のカーソル (中指の付け根)
                mcp_landmark = hand_landmarks.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_MCP]
                hand_pos = (int(mcp_landmark.x * SCREEN_WIDTH), int(mcp_landmark.y * SCREEN_HEIGHT))
                
                # ★デコピン判定用のカーソル (中指の先端)
                middle_tip = hand_landmarks.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_TIP]
                flick_pos_x = int(middle_tip.x * SCREEN_WIDTH)
                flick_pos_y = int(middle_tip.y * SCREEN_HEIGHT)

                if handedness.classification[0].label == 'Left':
                    left_is_grabbing = not is_open
                    left_cursor_pos[:] = hand_pos
                    left_flick_pos[:] = (flick_pos_x, flick_pos_y) 
                    
                    # ★デコピン速度計算
                    left_middle_tip_y[0] = left_middle_tip_y[1] 
                    left_middle_tip_y[1] = flick_pos_y         
                    flick_velocity = left_middle_tip_y[0] - left_middle_tip_y[1] 
                    
                    if is_open and flick_velocity > FLICK_THRESHOLD:
                        left_flick_detected = True

                elif handedness.classification[0].label == 'Right':
                    right_is_grabbing = not is_open
                    right_cursor_pos[:] = hand_pos
                    right_flick_pos[:] = (flick_pos_x, flick_pos_y) 

                    # ★デコピン速度計算
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
            max_y_world = world_y_offset + SCREEN_HEIGHT
            for hold_rect_world in holds_list:
                if hold_rect_world.bottom > min_y_world and hold_rect_world.top < max_y_world:
                    screen_rect = hold_rect_world.move(0, -world_y_offset)
                    visible_holds_for_drawing.append(screen_rect) 
                    
                    if left_colliding_hold is None and left_cursor_rect.colliderect(screen_rect):
                        left_colliding_hold = screen_rect
                    if right_colliding_hold is None and right_cursor_rect.colliderect(screen_rect):
                        right_colliding_hold = screen_rect

        # --- ★★★ 掴みとスクロールのロジック (修正) ★★★ ---
        left_can_grab = left_is_grabbing and (left_colliding_hold is not None)
        right_can_grab = right_is_grabbing and (right_colliding_hold is not None)
        
        # ★ 現フレームでの掴み状態
        # current_player_is_holding = left_can_grab or right_can_grab # ★削除

        # ★ 変更: 「新しく掴んだ手」があるかを判定し、その手の基準点をリセット
        left_grabbed_this_frame = left_can_grab and not left_was_holding
        right_grabbed_this_frame = right_can_grab and not right_was_holding

        # ★ 変更: どちらかの手が新しく掴んだ場合、ワールドの基準点を設定
        if left_grabbed_this_frame or right_grabbed_this_frame: 
            world_hold_start_y = world_y_offset
            # ★【最重要修正】
            # 新しい手が掴んだ時、すで掴んでいるもう片方の手も
            # 「現在のY座標」を基準点としてリセットする
            # これにより、基準点のズレによるジャンプを防ぐ
            if left_can_grab: # 左手は(すでに/新しく)掴んでいる
                left_hold_start_y = left_cursor_pos[1]
            if right_can_grab: # 右手は(すでに/新しく)掴んでいる
                right_hold_start_y = right_cursor_pos[1]
        
        # ★ 変更: 各手について、新しく掴んだ場合のみ手の基準点を設定
        #if left_grabbed_this_frame:
        #    left_hold_start_y = left_cursor_pos[1]
        #if right_grabbed_this_frame:
        #    right_hold_start_y = right_cursor_pos[1]

        # ★ 変更: 現在どちらかの手が掴んでいればプル処理
        if left_can_grab or right_can_grab:
            # プル距離を計算
            pull_distance_left = 0
            pull_distance_right = 0
            
            # ★ 変更: 「現在掴んでいる手」のプル距離のみ計算
            if left_can_grab:
                pull_distance_left = left_cursor_pos[1] - left_hold_start_y
            if right_can_grab:
                pull_distance_right = right_cursor_pos[1] - right_hold_start_y
                
            # 両手で掴んでいる場合、より大きく引いた方を採用
            pull_distance = max(pull_distance_left, pull_distance_right)
            
            if pull_distance < 0: pull_distance = 0
            if pull_distance > MAX_PULL_PIXELS: pull_distance = MAX_PULL_PIXELS
            
            world_y_offset = world_hold_start_y - pull_distance

        else: # どちらの手も掴んでいない
            world_y_offset += GRAVITY
        
        # ★ 変更: 次のフレームのために、現在の掴み状態を保存
        left_was_holding = left_can_grab
        right_was_holding = right_can_grab
        
        # スクロール範囲の制限
        if world_y_offset > max_scroll: world_y_offset = max_scroll
        if world_y_offset < 0: world_y_offset = 0

        # --- ★エネミーの更新と当たり判定 ---
        
        # ★デコピンの当たり判定用のRectを作成
        left_flick_rect = pygame.Rect(left_flick_pos[0] - cursor_radius, left_flick_pos[1] - cursor_radius, cursor_radius*2, cursor_radius*2)
        right_flick_rect = pygame.Rect(right_flick_pos[0] - cursor_radius, right_flick_pos[1] - cursor_radius, cursor_radius*2, cursor_radius*2)

        # ★リストのコピー( `[:]` )を使ってループ中に安全に削除する
        for enemy in enemy_list[:]:
            enemy.update()
            
            # ★ゲームオーバー判定
            if enemy.rect.top > SCREEN_HEIGHT:
                enemy_list.remove(enemy) # 画面外に出たら削除
                game_over = True         # ゲームオーバー
                break 
            
            # ★デコピンの当たり判定 (左手)
            if left_flick_detected and left_flick_rect.colliderect(enemy.rect):
                enemy_list.remove(enemy)
                # left_flick_detected = True # 描画用にTrueを維持 -> このフレームでしか使わないので不要
            
            # ★デコピンの当たり判定 (右手)
            elif right_flick_detected and right_flick_rect.colliderect(enemy.rect):
                enemy_list.remove(enemy)
                # right_flick_detected = True # 描画用にTrueを維持 -> このフレームでしか使わないので不要

        if game_over: # ★もしこのフレームでゲームオーバーになったら、ここで処理を中断
            pass 

        # 5. Pygameの描画処理
        if full_background:
            screen.blit(full_background, (0, -world_y_offset))
        else:
            screen.fill(SKY_BLUE)
        
        if hold_image:
            for rect in visible_holds_for_drawing:
                screen.blit(hold_image, rect)
        
        # ★エネミーを描画
        for enemy in enemy_list:
            enemy.draw(screen)

        # 高度表示UI
        height_climbed = (max_scroll - world_y_offset) / PIXELS_PER_METER
        height_text = font.render(f"Height: {height_climbed:.1f} m", True, BLACK)
        pygame.draw.rect(screen, WHITE, (5, 5, height_text.get_width() + 10, height_text.get_height()))
        screen.blit(height_text, (10, 5))
        
        # 左右の（掴み用）カーソルを描画
        left_cursor_color = GREEN if left_can_grab else RED
        right_cursor_color = GREEN if right_can_grab else RED
        
        # ★透明な円を描画するためのSurfaceを作成
        # RGBA形式で透明度を255段階で設定 (0:完全透明, 255:完全不透明)
        ALPHA_VALUE = 128 # ★透明度 (128は半透明)

        # 左手カーソル
        if left_cursor_pos[0] != -100: # 有効な座標の場合のみ描画
            circle_surface_left = pygame.Surface((cursor_radius * 2, cursor_radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(circle_surface_left, left_cursor_color + (ALPHA_VALUE,), (cursor_radius, cursor_radius), cursor_radius)
            screen.blit(circle_surface_left, (left_cursor_pos[0] - cursor_radius, left_cursor_pos[1] - cursor_radius))

        # 右手カーソル
        if right_cursor_pos[0] != -100: # 有効な座標の場合のみ描画
            circle_surface_right = pygame.Surface((cursor_radius * 2, cursor_radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(circle_surface_right, right_cursor_color + (ALPHA_VALUE,), (cursor_radius, cursor_radius), cursor_radius)
            screen.blit(circle_surface_right, (right_cursor_pos[0] - cursor_radius, right_cursor_pos[1] - cursor_radius))

        # ★デコピンのエフェクトを描画
        if left_flick_detected:
            pygame.draw.circle(screen, BLUE, left_flick_pos, cursor_radius + 10, 5) 
        if right_flick_detected:
            pygame.draw.circle(screen, BLUE, right_flick_pos, cursor_radius + 10, 5)

    else:
        # ★ゲームオーバー時の描画
        screen.fill(BLACK)
        go_text = game_over_font.render("GAME OVER", True, RED)
        screen.blit(go_text, (
            SCREEN_WIDTH // 2 - go_text.get_width() // 2,
            SCREEN_HEIGHT // 2 - go_text.get_height() // 2
        ))
        
    pygame.display.flip()
    clock.tick(60)

# --- 終了処理 ---
cap.release()
cv2.destroyAllWindows()
pygame.quit()