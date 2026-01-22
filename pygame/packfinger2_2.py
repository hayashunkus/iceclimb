import pygame
import cv2
import mediapipe as mp
import numpy as np
import sys

# ==========================================
# ユニバーサルデザイン・設定エリア
# 色やサイズはここで簡単に変更して検証できます
# ==========================================

# 画面設定
# マップ幅(28マス) * 40 = 1120
SCREEN_WIDTH = 1120
SCREEN_HEIGHT = 850 # 下部にカメラスペースを確保するため少し拡張
FPS = 60
BLOCK_SIZE = 40  # 1マスの大きさ

# カラーパレット (RGB)
COLORS = {
    'BACKGROUND': (255, 255, 255),   # 白（背景反転）
    'WALL': (205, 205, 55),          # 黄土色（青の補色側）
    'PLAYER': (0, 0, 255),           # 青（黄色の補色）
    'DOT': (0, 72, 81),              # 濃い青緑
    'ENEMY_RED': (0, 255, 255),      # シアン
    'ENEMY_BLUE': (255, 255, 0),     # 黄
    'ENEMY_GREEN': (255, 0, 255),    # マゼンタ
    'TEXT': (0, 0, 0),               # 黒
    'CAMERA_FRAME': (155, 155, 155), # 薄い灰色
    'BUTTON_START': (255, 75, 255),  # マゼンタ系
    'BUTTON_RESET': (55, 205, 205),  # シアン系
    'BUTTON_TEXT': (0, 0, 0)
}

# マップデータ (テキストで表現)
# W: 壁, .: エサ, P: プレイヤー, R/G/B: 敵, 空白: 通路(エサなし)
# SHUNKUSの文字を模したマップレイアウト
TILE_MAP = [
    "WWWWWWWWWWWWWWWWWWWWWWWWWWWW",
    "W..........................W",
    "W.WWWW.W..W.W..W.W..W.W..W.W", # S H U N K
    "W.W....W..W.W..W.WW.W.W.W..W",
    "W.WWWW.WWWW.W..W.W.WW.WW...W",
    "W....W.W..W.W..W.W..W.W.W..W",
    "W.WWWW.W..W.WWWW.W..W.W..W.W",
    "W..........................W",
    "W.WWWWWW.WWWWWW.WWWWWW.WWW.W",
    "                        ", # ワープゾーン用の中央通路
    "W.WWWWWW WWWWWW WWWWWW WWW.W",
    "W..........  P  ...........W", # Pはプレイヤー開始位置
    "WWWWWWWWWWWWWWWWWWWWWWWWWWWW"
]

# ==========================================
# システム初期化
# ==========================================

pygame.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Hand Gesture Pac-Man - Universal Design Test")
clock = pygame.time.Clock()
font = pygame.font.SysFont("arial", 24)
large_font = pygame.font.SysFont("arial", 64)
button_font = pygame.font.SysFont("arial", 32, bold=True)

# MediaPipeの手検出初期化
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    max_num_hands=1,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.5
)

# ==========================================
# クラス定義
# ==========================================

class Button:
    def __init__(self, x, y, width, height, text, color, text_color):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.color = color
        self.text_color = text_color
        self.original_color = color

    def draw(self, surface):
        # ボタン本体
        pygame.draw.rect(surface, self.color, self.rect)
        # 枠線
        pygame.draw.rect(surface, (255, 255, 255), self.rect, 2)
        # テキスト
        text_surf = button_font.render(self.text, True, self.text_color)
        text_rect = text_surf.get_rect(center=self.rect.center)
        surface.blit(text_surf, text_rect)

    def is_clicked(self, pos):
        return self.rect.collidepoint(pos)

class Entity(pygame.sprite.Sprite):
    def __init__(self, grid_x, grid_y, color):
        super().__init__()
        self.grid_x = grid_x
        self.grid_y = grid_y
        self.x = grid_x * BLOCK_SIZE
        self.y = grid_y * BLOCK_SIZE
        self.color = color
        self.speed = 4  # 割り切れる数推奨
        self.direction = (0, 0)
        self.next_direction = (0, 0)
        self.rect = pygame.Rect(self.x, self.y, BLOCK_SIZE, BLOCK_SIZE)

    def can_move(self, dx, dy, walls):
        center_x = self.x + BLOCK_SIZE // 2
        center_y = self.y + BLOCK_SIZE // 2
        
        next_grid_x = int((center_x + dx * BLOCK_SIZE) // BLOCK_SIZE)
        next_grid_y = int((center_y + dy * BLOCK_SIZE) // BLOCK_SIZE)
        
        if next_grid_x < 0 or next_grid_x >= len(TILE_MAP[0]):
            if dy != 0:
                return False
            return True

        if 0 <= next_grid_y < len(TILE_MAP) and 0 <= next_grid_x < len(TILE_MAP[0]):
            if walls[next_grid_y][next_grid_x] == 1:
                return False
        return True

    def update_pos(self, walls):
        on_grid_x = (self.x % BLOCK_SIZE) == 0
        on_grid_y = (self.y % BLOCK_SIZE) == 0
        
        if on_grid_x and on_grid_y:
            if self.next_direction != (0, 0):
                if self.can_move(self.next_direction[0], self.next_direction[1], walls):
                    self.direction = self.next_direction
            
            if not self.can_move(self.direction[0], self.direction[1], walls):
                self.direction = (0, 0)

        self.x += self.direction[0] * self.speed
        self.y += self.direction[1] * self.speed

        if self.x > SCREEN_WIDTH:
            self.x = -BLOCK_SIZE
        elif self.x < -BLOCK_SIZE:
            self.x = SCREEN_WIDTH

        self.rect.topleft = (self.x, self.y)

class Player(Entity):
    def __init__(self, grid_x, grid_y):
        super().__init__(grid_x, grid_y, COLORS['PLAYER'])
        self.score = 0

    def draw(self, surface):
        full_rect = pygame.Rect(self.x, self.y, BLOCK_SIZE, BLOCK_SIZE)
        pygame.draw.rect(surface, self.color, full_rect)
        
        bg_color = COLORS['BACKGROUND']
        mouth_size = BLOCK_SIZE // 2
        offset = (BLOCK_SIZE - mouth_size) // 2
        
        if self.direction == (1, 0):
            mouth_rect = pygame.Rect(self.x + BLOCK_SIZE - offset, self.y + offset, offset, mouth_size)
            pygame.draw.rect(surface, bg_color, mouth_rect)
        elif self.direction == (-1, 0):
            mouth_rect = pygame.Rect(self.x, self.y + offset, offset, mouth_size)
            pygame.draw.rect(surface, bg_color, mouth_rect)
        elif self.direction == (0, -1):
            mouth_rect = pygame.Rect(self.x + offset, self.y, mouth_size, offset)
            pygame.draw.rect(surface, bg_color, mouth_rect)
        elif self.direction == (0, 1):
            mouth_rect = pygame.Rect(self.x + offset, self.y + BLOCK_SIZE - offset, mouth_size, offset)
            pygame.draw.rect(surface, bg_color, mouth_rect)
        else:
            mouth_rect = pygame.Rect(self.x + BLOCK_SIZE - offset, self.y + offset, offset, mouth_size)
            pygame.draw.rect(surface, bg_color, mouth_rect)

class Ghost(Entity):
    def __init__(self, grid_x, grid_y, color_key):
        super().__init__(grid_x, grid_y, COLORS[color_key])
        self.speed = 2

    def update_pos(self, walls):
        on_grid_x = (self.x % BLOCK_SIZE) == 0
        on_grid_y = (self.y % BLOCK_SIZE) == 0

        if on_grid_x and on_grid_y:
            possible_directions = []
            for d in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
                if d == (-self.direction[0], -self.direction[1]) and self.direction != (0,0):
                    continue
                if self.can_move(d[0], d[1], walls):
                    possible_directions.append(d)
            
            if possible_directions:
                import random
                self.direction = random.choice(possible_directions)
            else:
                self.direction = (-self.direction[0], -self.direction[1])

        self.x += self.direction[0] * self.speed
        self.y += self.direction[1] * self.speed
        
        if self.x > SCREEN_WIDTH: self.x = -BLOCK_SIZE
        elif self.x < -BLOCK_SIZE: self.x = SCREEN_WIDTH
        
        self.rect.topleft = (self.x, self.y)

    def draw(self, surface):
        pygame.draw.rect(surface, self.color, self.rect)


# ==========================================
# ゲームのメインロジック
# ==========================================

def get_hand_direction(frame):
    """
    MediaPipeを使って手の方向（人差し指のベクトル）を検出する
    """
    image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(image_rgb)
    
    direction = (0, 0)
    debug_info = "No Hand"

    if results.multi_hand_landmarks:
        for hand_landmarks in results.multi_hand_landmarks:
            idx_mcp = hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_MCP]
            idx_tip = hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_TIP]
            
            dx = idx_tip.x - idx_mcp.x
            dy = idx_tip.y - idx_mcp.y
            
            threshold = 0.04
            
            if abs(dx) > abs(dy):
                if abs(dx) > threshold:
                    if dx > 0: # 画面上では左、自分目線で右
                        direction = (1, 0) 
                    else:
                        direction = (-1, 0)
            else:
                if abs(dy) > threshold:
                    if dy > 0:
                        direction = (0, 1)
                    else:
                        direction = (0, -1)
            
            if direction == (0, -1): debug_info = "UP"
            elif direction == (0, 1): debug_info = "DOWN"
            elif direction == (-1, 0): debug_info = "LEFT"
            elif direction == (1, 0): debug_info = "RIGHT"
            else: debug_info = "NEUTRAL"
            
            break 

    return direction, debug_info, results

def init_game_data():
    """ゲームのエンティティとマップデータを初期化して返す"""
    rows = len(TILE_MAP)
    cols = len(TILE_MAP[0])
    walls = [[0 for _ in range(cols)] for _ in range(rows)]
    dots = []
    enemies = []
    player = None

    for r, row in enumerate(TILE_MAP):
        for c, char in enumerate(row):
            if char == 'W':
                walls[r][c] = 1
            elif char == '.':
                dots.append(pygame.Rect(c * BLOCK_SIZE + BLOCK_SIZE//2 - 4, r * BLOCK_SIZE + BLOCK_SIZE//2 - 4, 8, 8))
            elif char == 'P':
                player = Player(c, r)
            elif char == 'R':
                enemies.append(Ghost(c, r, 'ENEMY_RED'))
            elif char == 'B':
                enemies.append(Ghost(c, r, 'ENEMY_BLUE'))
            elif char == 'G':
                enemies.append(Ghost(c, r, 'ENEMY_GREEN'))
    
    if not enemies:
        enemies.append(Ghost(1, 1, 'ENEMY_RED'))
        enemies.append(Ghost(cols-2, 1, 'ENEMY_BLUE'))
        enemies.append(Ghost(cols-2, rows-2, 'ENEMY_GREEN'))
    
    return walls, dots, enemies, player, rows

def main():
    cap = cv2.VideoCapture(0)
    
    # ゲームデータの初期化
    walls, dots, enemies, player, rows = init_game_data()

    # ゲーム状態管理
    running = True
    game_active = False # スタートボタンを押すまでFalse
    game_over = False
    game_clear = False
    
    current_direction_name = "STOP"

    # マップ下のY座標基準
    map_bottom_y = rows * BLOCK_SIZE

    # UIボタンの作成
    btn_width = 160
    btn_height = 60
    btn_x = 50 # 左側に配置
    
    # スタートボタン (上)
    start_btn = Button(btn_x, map_bottom_y + 30, btn_width, btn_height, 
                       "START", COLORS['BUTTON_START'], COLORS['BUTTON_TEXT'])
    
    # リセットボタン (下)
    reset_btn = Button(btn_x, map_bottom_y + 30 + btn_height + 20, btn_width, btn_height, 
                       "RESET", COLORS['BUTTON_RESET'], COLORS['BUTTON_TEXT'])

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
            
            # マウスクリック処理
            if event.type == pygame.MOUSEBUTTONDOWN:
                # スタートボタン
                if start_btn.is_clicked(event.pos):
                    if not game_active:
                        # ゲーム開始
                        game_active = True
                    # 終了後に押した場合はリスタート
                    elif game_over or game_clear:
                        walls, dots, enemies, player, rows = init_game_data()
                        game_active = True
                        game_over = False
                        game_clear = False
                
                # リセットボタン
                if reset_btn.is_clicked(event.pos):
                    # 強制リセットして待機状態へ
                    walls, dots, enemies, player, rows = init_game_data()
                    game_active = False
                    game_over = False
                    game_clear = False
                    current_direction_name = "STOP"

        # --- カメラ処理 ---
        ret, frame = cap.read()
        if not ret:
            print("カメラが見つかりません")
            break
        frame = cv2.flip(frame, 1)
        
        # ハンドジェスチャー認識
        hand_dir, debug_str, mp_results = get_hand_direction(frame)
        
        # プレイ中のみ入力を受け付ける
        if game_active and not game_over and not game_clear:
            current_direction_name = debug_str
            if hand_dir != (0, 0):
                player.next_direction = hand_dir
        
        # --- ゲーム更新 ---
        if game_active and not game_over and not game_clear:
            player.update_pos(walls)
            
            # ドット判定
            player_center = player.rect.center
            hitbox = player.rect.inflate(-10, -10)
            new_dots = []
            for dot in dots:
                if hitbox.colliderect(dot):
                    player.score += 10
                else:
                    new_dots.append(dot)
            dots = new_dots
            
            if len(dots) == 0:
                game_clear = True

            # 敵判定
            for enemy in enemies:
                enemy.update_pos(walls)
                if hitbox.colliderect(enemy.rect):
                    game_over = True

        # --- 描画 ---
        screen.fill(COLORS['BACKGROUND'])

        # マップ描画
        for r in range(rows):
            for c in range(len(walls[0])):
                if walls[r][c] == 1:
                    pygame.draw.rect(screen, COLORS['WALL'], 
                                     (c * BLOCK_SIZE, r * BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE))

        for dot in dots:
            pygame.draw.circle(screen, COLORS['DOT'], dot.center, 5)

        for enemy in enemies:
            enemy.draw(screen)

        player.draw(screen)

        # UI: スコア
        score_text = font.render(f"SCORE: {player.score}", True, COLORS['TEXT'])
        screen.blit(score_text, (10, 10))

        # UI: ボタン
        start_btn.draw(screen)
        reset_btn.draw(screen)

        # UI: カメラパネル (中央)
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        if mp_results.multi_hand_landmarks:
             mp.solutions.drawing_utils.draw_landmarks(
                frame, mp_results.multi_hand_landmarks[0], mp_hands.HAND_CONNECTIONS)
        
        frame = np.rot90(frame) 
        frame = pygame.surfarray.make_surface(frame)
        
        camera_display_width = 320
        camera_display_height = 240
        frame = pygame.transform.scale(frame, (camera_display_width, camera_display_height))
        
        panel_x = (SCREEN_WIDTH - camera_display_width) // 2
        panel_y = map_bottom_y + 30
        
        pygame.draw.rect(screen, COLORS['CAMERA_FRAME'], 
                        (panel_x - 5, panel_y - 5, camera_display_width + 10, camera_display_height + 10), 3)
        screen.blit(frame, (panel_x, panel_y))
        
        # UI: 方向インジケータ
        dir_text = font.render(f"INPUT: {current_direction_name}", True, COLORS['TEXT'])
        text_rect = dir_text.get_rect(center=(SCREEN_WIDTH // 2, panel_y + camera_display_height + 30))
        screen.blit(dir_text, text_rect)

        # UI: ゲームステータス表示
        if game_over:
            text = large_font.render("GAME OVER", True, (255, 0, 0))
            text_rect = text.get_rect(center=(SCREEN_WIDTH/2, SCREEN_HEIGHT/2))
            screen.blit(text, text_rect)
        elif game_clear:
            text = large_font.render("CLEAR!", True, (255, 255, 0))
            text_rect = text.get_rect(center=(SCREEN_WIDTH/2, SCREEN_HEIGHT/2))
            screen.blit(text, text_rect)
        elif not game_active:
            # 待機中メッセージ
            msg = large_font.render("PRESS START", True, (0, 255, 0))
            msg_rect = msg.get_rect(center=(SCREEN_WIDTH/2, SCREEN_HEIGHT/2))
            screen.blit(msg, msg_rect)

        pygame.display.flip()
        clock.tick(FPS)

    cap.release()
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()