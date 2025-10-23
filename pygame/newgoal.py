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
TOTAL_CLIMB_METERS = 105.0 # ★ 修正: 100.0 -> 105.0
MAX_PULL_METERS = 2.0
# ★ ゴール判定用の設定
GOAL_THRESHOLD_METERS = 98.0 # ★ 修正: 97.0 -> 100.0 (100mで背景変更)
GOAL_ZONE_METERS = 5.0 # ★ 修正: 3.0 -> 5.0 (最後の5mはホールド無し)

TOTAL_CLIMB_PIXELS = int(TOTAL_CLIMB_METERS * PIXELS_PER_METER)
MAX_PULL_PIXELS = int(MAX_PULL_METERS * PIXELS_PER_METER)
GRAVITY = 10 # 落下速度 (10のまま)

# Pygameウィンドウの設定
SCREEN_WIDTH, SCREEN_HEIGHT = 1280, 720
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption(f"Bouldering Game ({int(TOTAL_CLIMB_METERS-5)}m Climb)") # ★ タイトルも105mに

# 色とフォントの定義
WHITE = (255, 255, 255)
RED = (255, 0, 0)
GREEN = (0, 255, 0) # 掴んだ時の色
BLACK = (0, 0, 0)
SKY_BLUE = (135, 206, 235)
BLUE = (0, 0, 255) # ★デコピンのエフェクト色
font = pygame.font.Font(None, 50)
game_over_font = pygame.font.Font(None, 100) # ★ゲームオーバー用フォント

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
    # 画面サイズに合わせてスケーリング
    goal_background_image = pygame.transform.scale(img, (SCREEN_WIDTH, SCREEN_HEIGHT))
except FileNotFoundError:
    print("エラー: image/goaliceclimb.png が見つかりません。")

# ★ ダンサーアニメーション画像の読み込み
dancer_images = []
dancer_frame = 0
dancer_frame_time = 0
ANIMATION_SPEED_MS = 100 # 1フレームあたり100ミリ秒
try:
    for i in range(1, 6):
        img_path = f"image/c-dancer-{i}.png"
        img = pygame.image.load(img_path).convert_alpha() # ★ 画像を読み込み
        # ★ ダンサー画像をリサイズ (300x300)
        img = pygame.transform.scale(img, (300, 300)) # ★
        dancer_images.append(img) # ★ リサイズした画像を追加
except FileNotFoundError as e:
    print(f"エラー: ダンサー画像が見つかりません。 {e}")


# ★エネミー管理リスト
enemy_list = [] 

# ★エネミー出現イベント (5000ms = 5ごと)
ENEMY_SPAWN_EVENT = pygame.USEREVENT + 1
pygame.time.set_timer(ENEMY_SPAWN_EVENT, 5000)

# プレイヤー（カーソル）の設定 (左右別々に)
left_cursor_pos = [-100, -100]
right_cursor_pos = [-100, -100]
cursor_radius = 45 # ★半径を45に設定

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
    
    # ★ 変更: ゴールゾーン（上部）にはホールドを生成しない
    GOAL_ZONE_PIXELS = GOAL_ZONE_METERS * PIXELS_PER_METER # 5m * 360 = 1800 pixels

    current_y = TOTAL_CLIMB_PIXELS - (SCREEN_HEIGHT // 2)
    side = 0 
    
    # ★ 変更: current_y が GOAL_ZONE_PIXELS より大きい間のみ生成
    while current_y > GOAL_ZONE_PIXELS: 
        y_variation = random.randint(-PIXELS_PER_METER // 4, PIXELS_PER_METER // 4)
        h_y = current_y + y_variation
        # ゴールゾーンにはみ出さないように再チェック
        if h_y < GOAL_ZONE_PIXELS:
             h_y = GOAL_ZONE_PIXELS + random.randint(10, 50)

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
left_was_holding = False
right_was_holding = False
left_hold_start_y = 0
right_hold_start_y = 0
world_hold_start_y = 0

# --- ★ゲーム状態の管理 ---
game_over = False
game_won = False # ★追加: ゲームクリアフラグ
is_near_goal = False # ★変更: この変数はゴール判定のみに使う

# --- 関数定義 ---
def is_hand_open(hand_landmarks):
    tip_ids = [mp_hands.HandLandmark.INDEX_FINGER_TIP, mp_hands.HandLandmark.MIDDLE_FINGER_TIP, mp_hands.HandLandmark.RING_FINGER_TIP, mp_hands.HandLandmark.PINKY_TIP]
    pip_ids = [mp_hands.HandLandmark.INDEX_FINGER_PIP, mp_hands.HandLandmark.MIDDLE_FINGER_PIP, mp_hands.HandLandmark.RING_FINGER_PIP, mp_hands.HandLandmark.PINKY_PIP]
    open_fingers = sum(1 for tip_id, pip_id in zip(tip_ids, pip_ids) if hand_landmarks.landmark[tip_id].y < hand_landmarks.landmark[pip_id].y)
    return open_fingers >= 3

# --- メインループ ---
running = True
clock = pygame.time.Clock()

while running:
    # 1. イベント処理 (常に実行)
    # ★ is_near_goal の計算を移動させたため、イベント処理でのチェックを修正
    
    # ★ height_climbed を先に計算（イベント処理で使うため）
    # (ただし、max_scroll が未定義だとエラーになるため、メインループ初回以降は大丈夫)
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
                current_max_scroll = (int(TOTAL_CLIMB_METERS * PIXELS_PER_METER)) - SCREEN_HEIGHT
                
                warp_y_offset = current_max_scroll - (warp_height_meters * PIXELS_PER_METER)
                
                if warp_y_offset < 0: warp_y_offset = 0
                if warp_y_offset > current_max_scroll: warp_y_offset = current_max_scroll
                
                world_y_offset = warp_y_offset
                left_was_holding = False
                right_was_holding = False
                print(f"ロケット！ 90m地点 (y_offset: {world_y_offset}) へワープします。")

        
        # ★ 変更: is_near_goal は上で計算済み
        if event.type == ENEMY_SPAWN_EVENT and not game_over and not game_won and not is_near_goal:
            if enemy_image: # 画像が読み込めていれば
                enemy_list.append(Enemy(enemy_image))

    # ★ ゲーム状態によって処理を分岐 ★
    if game_won:
        # --- ★★★ GAME CLEAR ★★★ ---
        
        # ゴール背景を描画
        if goal_background_image:
            screen.blit(goal_background_image, (0, 0))
        else:
            screen.fill(SKY_BLUE) # 代替

        # ★ 登頂おめでとうテキスト
        goal_text = game_over_font.render("100m Climb Success!!", True, BLACK)
        screen.blit(goal_text, (
            SCREEN_WIDTH // 2 - goal_text.get_width() // 2,
            SCREEN_HEIGHT // 4 - goal_text.get_height() // 2
        ))

        # ダンサーアニメーション
        if dancer_images:
            # フレーム更新
            dancer_frame_time += clock.get_time()
            if dancer_frame_time > ANIMATION_SPEED_MS:
                dancer_frame = (dancer_frame + 1) % len(dancer_images)
                dancer_frame_time = 0
            
            # 描画
            current_dancer_image = dancer_images[dancer_frame]
            # 画面中央に配置
            img_rect = current_dancer_image.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 50)) # ★ 少し下に
            screen.blit(current_dancer_image, img_rect)
        
        # OpenCVウィンドウを閉じる
        if cv2.getWindowProperty('MediaPipe Hands', cv2.WND_PROP_VISIBLE) >= 1:
            cv2.destroyWindow('MediaPipe Hands')

    elif not game_over:
        # --- ★★★ GAME RUNNING ★★★ ---

        # ★ 変更: height_climbed と is_near_goal は既に計算済み
        if is_near_goal:
            game_won = True # ★★★ ゲームクリア ★★★
            # ★ ゴールしたら、このフレームの残りのゲームロジックをスキップ
            pygame.display.flip() # 画面だけ更新して
            continue # 次のループへ (game_wonブロックが実行される)

        if not cap.isOpened():
            break

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

        # 4. ジェスチャーとゲームロジック (左右分離)
        
        # 状態をリセット
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
                hand_pos = (int(mcp_landmark.x * SCREEN_WIDTH), int(mcp_landmark.y * SCREEN_HEIGHT))
                
                middle_tip = hand_landmarks.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_TIP]
                flick_pos_x = int(middle_tip.x * SCREEN_WIDTH)
                flick_pos_y = int(middle_tip.y * SCREEN_HEIGHT)

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
            max_y_world = world_y_offset + SCREEN_HEIGHT
            for hold_rect_world in holds_list:
                if hold_rect_world.bottom > min_y_world and hold_rect_world.top < max_y_world:
                    screen_rect = hold_rect_world.move(0, -world_y_offset)
                    visible_holds_for_drawing.append(screen_rect) 
                    
                    if left_colliding_hold is None and left_cursor_rect.colliderect(screen_rect):
                        left_colliding_hold = screen_rect
                    if right_colliding_hold is None and right_cursor_rect.colliderect(screen_rect):
                        right_colliding_hold = screen_rect

        # --- ★★★ 掴みとスクロールのロジック (V3のまま) ★★★ ---
        left_can_grab = left_is_grabbing and (left_colliding_hold is not None)
        right_can_grab = right_is_grabbing and (right_colliding_hold is not None)
        
        left_grabbed_this_frame = left_can_grab and not left_was_holding
        right_grabbed_this_frame = right_can_grab and not right_was_holding

        if left_grabbed_this_frame or right_grabbed_this_frame: 
            world_hold_start_y = world_y_offset
            if left_can_grab:
                left_hold_start_y = left_cursor_pos[1]
            if right_can_grab:
                right_hold_start_y = right_cursor_pos[1]

        if left_can_grab or right_can_grab:
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
            world_y_offset += GRAVITY
        
        left_was_holding = left_can_grab
        right_was_holding = right_can_grab
        
        # スクロール範囲の制限
        if world_y_offset > max_scroll: world_y_offset = max_scroll
        
        # ★ 変更: ゴール判定を上部へ移動したため削除
        # if world_y_offset <= 0: ...
        
        # --- ★エネミーの更新と当たり判定 ---
        # ★ is_near_goal は上で計算済み
        if not is_near_goal: # 100m未満の場合のみ
            left_flick_rect = pygame.Rect(left_flick_pos[0] - cursor_radius, left_flick_pos[1] - cursor_radius, cursor_radius*2, cursor_radius*2)
            right_flick_rect = pygame.Rect(right_flick_pos[0] - cursor_radius, right_flick_pos[1] - cursor_radius, cursor_radius*2, cursor_radius*2)

            for enemy in enemy_list[:]:
                enemy.update()
                
                if enemy.rect.top > SCREEN_HEIGHT:
                    enemy_list.remove(enemy) 
                    game_over = True         
                    break 
                
                if left_flick_detected and left_flick_rect.colliderect(enemy.rect):
                    enemy_list.remove(enemy)
                
                elif right_flick_detected and right_flick_rect.colliderect(enemy.rect):
                    enemy_list.remove(enemy)

        if game_over: 
            pass 

        # 5. Pygameの描画処理
        
        # 背景の描画
        if full_background:
            screen.blit(full_background, (0, -world_y_offset))
        else:
            screen.fill(SKY_BLUE)
        
        # ★ 高度計算と is_near_goal 判定は上に移動済み

        # ★ 描画ロジックを簡素化 (is_near_goal での背景切り替えを削除)
        # ★ 100m未満なら通常通り描画
        if hold_image:
            for rect in visible_holds_for_drawing:
                screen.blit(hold_image, rect)
        
        for enemy in enemy_list:
            enemy.draw(screen)

        # 高度表示UI (常に手前に表示)
        height_text_str = f"Height: {height_climbed:.1f} m"
        
        climbable_max_height = max_scroll / PIXELS_PER_METER # 103.0m
        if height_climbed >= climbable_max_height: 
             height_text_str = f"Height: {TOTAL_CLIMB_METERS:.1f} m GOAL!" # 105.0mと表示
             
        height_text = font.render(height_text_str, True, BLACK)
        pygame.draw.rect(screen, WHITE, (5, 5, height_text.get_width() + 10, height_text.get_height()))
        screen.blit(height_text, (10, 5))
        
        # 左右の（掴み用）カーソルを描画 (常に手前に表示)
        left_cursor_color = GREEN if left_can_grab else RED
        right_cursor_color = GREEN if right_can_grab else RED
        ALPHA_VALUE = 128 

        if left_cursor_pos[0] != -100: 
            circle_surface_left = pygame.Surface((cursor_radius * 2, cursor_radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(circle_surface_left, left_cursor_color + (ALPHA_VALUE,), (cursor_radius, cursor_radius), cursor_radius)
            screen.blit(circle_surface_left, (left_cursor_pos[0] - cursor_radius, left_cursor_pos[1] - cursor_radius))

        if right_cursor_pos[0] != -100: 
            circle_surface_right = pygame.Surface((cursor_radius * 2, cursor_radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(circle_surface_right, right_cursor_color + (ALPHA_VALUE,), (cursor_radius, cursor_radius), cursor_radius)
            screen.blit(circle_surface_right, (right_cursor_pos[0] - cursor_radius, right_cursor_pos[1] - cursor_radius))

        # ★デコピンのエフェクトを描画 (100m未満)
        if not is_near_goal: # is_near_goal は上で計算済み
            if left_flick_detected:
                pygame.draw.circle(screen, BLUE, left_flick_pos, cursor_radius + 10, 5) 
            if right_flick_detected:
                pygame.draw.circle(screen, BLUE, right_flick_pos, cursor_radius + 10, 5)

    else:
        # --- ★★★ GAME OVER ★★★ ---
        screen.fill(BLACK)
        go_text = game_over_font.render("GAME OVER", True, RED)
        screen.blit(go_text, (
            SCREEN_WIDTH // 2 - go_text.get_width() // 2,
            SCREEN_HEIGHT // 2 - go_text.get_height() // 2
        ))
        
        # OpenCVウィンドウを閉じる
        if cv2.getWindowProperty('MediaPipe Hands', cv2.WND_PROP_VISIBLE) >= 1:
            cv2.destroyWindow('MediaPipe Hands')

    # 画面更新 (全状態共通)
    pygame.display.flip()
    clock.tick(60)

# --- 終了処理 ---
cap.release()
cv2.destroyAllWindows()
pygame.quit()

