import pygame
import cv2
import mediapipe as mp
import numpy as np
import sys

# ==========================================
# ユニバーサルデザイン・設定エリア
# ==========================================

# 画面設定
MAP_WIDTH = 1120       # マップ部分の幅
SIDEBAR_WIDTH = 230    # 右側のボタンエリア
SCREEN_WIDTH = MAP_WIDTH + SIDEBAR_WIDTH
SCREEN_HEIGHT = 850
FPS = 60
BLOCK_SIZE = 40

# --- カラーパレット定義 ---
COLOR_PALETTES = {
    'NORMAL': {
        'NAME': 'Normal',
        'BACKGROUND': (0, 0, 0),
        'WALL': (50, 50, 200),
        'PLAYER': (255, 255, 0),
        'DOT': (255, 183, 174),
        'ENEMY_RED': (255, 0, 0),
        'ENEMY_BLUE': (0, 0, 255),
        'ENEMY_GREEN': (0, 255, 0),
        'TEXT': (255, 255, 255),
        'CAMERA_FRAME': (100, 100, 100),
        'BUTTON_START': (0, 180, 0),
        'BUTTON_RESET': (200, 50, 50),
        'BUTTON_TEXT': (255, 255, 255),
        'PANEL_BG': (50, 50, 50) # サイドバー背景
    },
    'INVERTED': {
        'NAME': 'Inverted',
        'BACKGROUND': (255, 255, 255),
        'WALL': (205, 205, 55),
        'PLAYER': (0, 0, 255),
        'DOT': (0, 72, 81),
        'ENEMY_RED': (0, 255, 255),
        'ENEMY_BLUE': (255, 255, 0),
        'ENEMY_GREEN': (255, 0, 255),
        'TEXT': (0, 0, 0),
        'CAMERA_FRAME': (155, 155, 155),
        'BUTTON_START': (255, 75, 255),
        'BUTTON_RESET': (55, 205, 205),
        'BUTTON_TEXT': (0, 0, 0),
        'PANEL_BG': (200, 200, 200)
    },
    'CUD': {
        'NAME': 'CUD (Easy)',
        'BACKGROUND': (0, 0, 0),
        'WALL': (0, 75, 150),           # 識別しやすい青
        'PLAYER': (255, 255, 0),        # 黄
        'DOT': (255, 255, 255),         # 白
        'ENEMY_RED': (255, 75, 0),      # 朱色（オレンジ寄り）
        'ENEMY_BLUE': (0, 100, 200),    # 空色
        'ENEMY_GREEN': (0, 153, 115),   # 青緑
        'TEXT': (255, 255, 255),
        'CAMERA_FRAME': (127, 135, 143),
        'BUTTON_START': (0, 153, 115),
        'BUTTON_RESET': (255, 153, 0),
        'BUTTON_TEXT': (255, 255, 255),
        'PANEL_BG': (40, 40, 45)
    }
}

# マップデータ
TILE_MAP = [
    "WWWWWWWWWWWWWWWWWWWWWWWWWWWW",
    "W..........................W",
    "W.WWWW.W..W.W..W.W..W.W..W.W",
    "W.W....W..W.W..W.WW.W.W.W..W",
    "W.WWWW.WWWW.W..W.W.WW.WW...W",
    "W....W.W..W.W..W.W..W.W.W..W",
    "W.WWWW.W..W.WWWW.W..W.W..W.W",
    "W..........................W",
    "W.WWWWWW.WWWWWW.WWWWWW.WWW.W",
    "                        ",
    "W.WWWWWW.WWWWWW.WWWWWW.WWW.W",
    "W............P.............W",
    "WWWWWWWWWWWWWWWWWWWWWWWWWWWW"
]

# ==========================================
# システム初期化
# ==========================================

pygame.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Hand Gesture Pac-Man - Color Palette Switcher")
clock = pygame.time.Clock()
font = pygame.font.SysFont("arial", 24)
large_font = pygame.font.SysFont("arial", 64)
button_font = pygame.font.SysFont("arial", 20, bold=True)
title_font = pygame.font.SysFont("arial", 28, bold=True)

# MediaPipe
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
    def __init__(self, x, y, width, height, text, color_key=None, text_color_key='BUTTON_TEXT', fixed_color=None):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.color_key = color_key         # パレットから色を取得する場合のキー
        self.text_color_key = text_color_key
        self.fixed_color = fixed_color     # 固定色を使う場合 (パレット切り替えボタン用など)

    def draw(self, surface, current_colors, is_selected=False):
        # 背景色決定
        if self.fixed_color:
            bg_color = self.fixed_color
        elif self.color_key:
            bg_color = current_colors[self.color_key]
        else:
            bg_color = (100, 100, 100) # デフォルト

        # 選択状態なら枠を強調
        line_width = 4 if is_selected else 2
        border_color = (255, 255, 0) if is_selected else (200, 200, 200)

        pygame.draw.rect(surface, bg_color, self.rect)
        pygame.draw.rect(surface, border_color, self.rect, line_width)
        
        # テキスト色
        if self.text_color_key and self.text_color_key in current_colors:
            txt_col = current_colors[self.text_color_key]
        else:
            txt_col = (255, 255, 255)

        text_surf = button_font.render(self.text, True, txt_col)
        text_rect = text_surf.get_rect(center=self.rect.center)
        surface.blit(text_surf, text_rect)

    def is_clicked(self, pos):
        return self.rect.collidepoint(pos)

class Entity(pygame.sprite.Sprite):
    def __init__(self, grid_x, grid_y, color_key):
        super().__init__()
        self.grid_x = grid_x
        self.grid_y = grid_y
        self.x = grid_x * BLOCK_SIZE
        self.y = grid_y * BLOCK_SIZE
        self.color_key = color_key # 色そのものではなくキーを保存
        self.speed = 4
        self.direction = (0, 0)
        self.next_direction = (0, 0)
        self.rect = pygame.Rect(self.x, self.y, BLOCK_SIZE, BLOCK_SIZE)

    def can_move(self, dx, dy, walls):
        center_x = self.x + BLOCK_SIZE // 2
        center_y = self.y + BLOCK_SIZE // 2
        next_grid_x = int((center_x + dx * BLOCK_SIZE) // BLOCK_SIZE)
        next_grid_y = int((center_y + dy * BLOCK_SIZE) // BLOCK_SIZE)
        
        if next_grid_x < 0 or next_grid_x >= len(TILE_MAP[0]):
            if dy != 0: return False
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

        if self.x > MAP_WIDTH: self.x = -BLOCK_SIZE
        elif self.x < -BLOCK_SIZE: self.x = MAP_WIDTH

        self.rect.topleft = (self.x, self.y)

class Player(Entity):
    def __init__(self, grid_x, grid_y):
        super().__init__(grid_x, grid_y, 'PLAYER')
        self.score = 0

    def draw(self, surface, current_colors):
        # 現在のパレットから色を取得
        color = current_colors[self.color_key]
        bg_color = current_colors['BACKGROUND']
        
        full_rect = pygame.Rect(self.x, self.y, BLOCK_SIZE, BLOCK_SIZE)
        pygame.draw.rect(surface, color, full_rect)
        
        mouth_size = BLOCK_SIZE // 2
        offset = (BLOCK_SIZE - mouth_size) // 2
        
        # 口の描画（背景色で塗りつぶす）
        mouth_rect = None
        if self.direction == (1, 0):
            mouth_rect = pygame.Rect(self.x + BLOCK_SIZE - offset, self.y + offset, offset, mouth_size)
        elif self.direction == (-1, 0):
            mouth_rect = pygame.Rect(self.x, self.y + offset, offset, mouth_size)
        elif self.direction == (0, -1):
            mouth_rect = pygame.Rect(self.x + offset, self.y, mouth_size, offset)
        elif self.direction == (0, 1):
            mouth_rect = pygame.Rect(self.x + offset, self.y + BLOCK_SIZE - offset, mouth_size, offset)
        else:
            mouth_rect = pygame.Rect(self.x + BLOCK_SIZE - offset, self.y + offset, offset, mouth_size)
            
        if mouth_rect:
            pygame.draw.rect(surface, bg_color, mouth_rect)

class Ghost(Entity):
    def __init__(self, grid_x, grid_y, color_key):
        super().__init__(grid_x, grid_y, color_key)
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
        
        if self.x > MAP_WIDTH: self.x = -BLOCK_SIZE
        elif self.x < -BLOCK_SIZE: self.x = MAP_WIDTH
        
        self.rect.topleft = (self.x, self.y)

    def draw(self, surface, current_colors):
        color = current_colors[self.color_key]
        pygame.draw.rect(surface, color, self.rect)

# ==========================================
# 関数
# ==========================================

def get_hand_direction(frame):
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
                    if dx > 0: direction = (1, 0) 
                    else: direction = (-1, 0)
            else:
                if abs(dy) > threshold:
                    if dy > 0: direction = (0, 1)
                    else: direction = (0, -1)
            
            if direction == (0, -1): debug_info = "UP"
            elif direction == (0, 1): debug_info = "DOWN"
            elif direction == (-1, 0): debug_info = "LEFT"
            elif direction == (1, 0): debug_info = "RIGHT"
            else: debug_info = "NEUTRAL"
            break 
    return direction, debug_info, results

def init_game_data():
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
    walls, dots, enemies, player, rows = init_game_data()

    # ゲーム状態
    running = True
    game_active = False
    game_over = False
    game_clear = False
    current_direction_name = "STOP"

    # カラーパレット状態
    current_palette_key = 'NORMAL'
    current_colors = COLOR_PALETTES[current_palette_key]

    # マップ下のY座標基準
    map_bottom_y = rows * BLOCK_SIZE

    # --- UI要素の作成 ---
    
    # ゲームコントロールボタン (マップ下)
    btn_width = 160
    btn_height = 60
    btn_x = 50 
    
    start_btn = Button(btn_x, map_bottom_y + 30, btn_width, btn_height, 
                       "START", color_key='BUTTON_START')
    reset_btn = Button(btn_x, map_bottom_y + 30 + btn_height + 20, btn_width, btn_height, 
                       "RESET", color_key='BUTTON_RESET')

    # パレット切り替えボタン (右サイドバー)
    palette_btn_x = MAP_WIDTH + 20
    palette_btn_y_start = 100
    palette_btn_width = 190
    palette_btn_height = 50
    
    palette_btns = [
        Button(palette_btn_x, palette_btn_y_start, palette_btn_width, palette_btn_height, 
               "Normal (Standard)", fixed_color=(200, 200, 200), text_color_key=None),
        
        Button(palette_btn_x, palette_btn_y_start + 70, palette_btn_width, palette_btn_height, 
               "Inverted (Complement)", fixed_color=(50, 50, 50), text_color_key=None),
               
        Button(palette_btn_x, palette_btn_y_start + 140, palette_btn_width, palette_btn_height, 
               "CUD (Easy View)", fixed_color=(0, 153, 115), text_color_key=None)
    ]
    # ボタンに対応するパレットキーを紐づけ
    palette_btns[0].target_key = 'NORMAL'
    palette_btns[1].target_key = 'INVERTED'
    palette_btns[2].target_key = 'CUD'

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
            
            if event.type == pygame.MOUSEBUTTONDOWN:
                # ゲームボタン
                if start_btn.is_clicked(event.pos):
                    if not game_active:
                        game_active = True
                    elif game_over or game_clear:
                        walls, dots, enemies, player, rows = init_game_data()
                        game_active = True
                        game_over = False
                        game_clear = False
                
                if reset_btn.is_clicked(event.pos):
                    walls, dots, enemies, player, rows = init_game_data()
                    game_active = False
                    game_over = False
                    game_clear = False
                    current_direction_name = "STOP"
                
                # パレット切り替えボタン
                for btn in palette_btns:
                    if btn.is_clicked(event.pos):
                        current_palette_key = btn.target_key
                        current_colors = COLOR_PALETTES[current_palette_key]

        # --- ロジック更新 ---
        ret, frame = cap.read()
        if not ret: break
        frame = cv2.flip(frame, 1)
        hand_dir, debug_str, mp_results = get_hand_direction(frame)
        
        if game_active and not game_over and not game_clear:
            current_direction_name = debug_str
            if hand_dir != (0, 0):
                player.next_direction = hand_dir
            
            player.update_pos(walls)
            
            hitbox = player.rect.inflate(-10, -10)
            new_dots = []
            for dot in dots:
                if hitbox.colliderect(dot):
                    player.score += 10
                else:
                    new_dots.append(dot)
            dots = new_dots
            
            if len(dots) == 0: game_clear = True

            for enemy in enemies:
                enemy.update_pos(walls)
                if hitbox.colliderect(enemy.rect):
                    game_over = True

        # --- 描画 ---
        # 背景
        screen.fill(current_colors['PANEL_BG']) # 全体背景(サイドバー含む)
        
        # マップエリア背景
        map_rect = pygame.Rect(0, 0, MAP_WIDTH, SCREEN_HEIGHT)
        pygame.draw.rect(screen, current_colors['BACKGROUND'], map_rect)

        # 壁描画
        for r in range(rows):
            for c in range(len(walls[0])):
                if walls[r][c] == 1:
                    pygame.draw.rect(screen, current_colors['WALL'], 
                                     (c * BLOCK_SIZE, r * BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE))

        # ドット
        for dot in dots:
            pygame.draw.circle(screen, current_colors['DOT'], dot.center, 5)

        # キャラクター (現在のパレットを渡して描画)
        for enemy in enemies:
            enemy.draw(screen, current_colors)
        player.draw(screen, current_colors)

        # --- サイドバー (右側) ---
        sidebar_x = MAP_WIDTH + 10
        
        # タイトル
        title_text = title_font.render("Color Palettes", True, (255, 255, 255))
        screen.blit(title_text, (sidebar_x, 50))
        
        # パレットボタン描画
        for btn in palette_btns:
            # 現在選択中のボタンを強調表示
            is_selected = (btn.target_key == current_palette_key)
            btn.draw(screen, current_colors, is_selected)
        
        # 現在のパレット名表示
        mode_text = font.render(f"Mode: {current_colors['NAME']}", True, (255, 255, 255))
        screen.blit(mode_text, (sidebar_x, 300))

        # --- マップ下部エリア ---
        # スコア
        score_text = font.render(f"SCORE: {player.score}", True, current_colors['TEXT'])
        screen.blit(score_text, (10, 10))

        # ゲームボタン
        start_btn.draw(screen, current_colors)
        reset_btn.draw(screen, current_colors)

        # カメラ
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        if mp_results.multi_hand_landmarks:
             mp.solutions.drawing_utils.draw_landmarks(
                frame, mp_results.multi_hand_landmarks[0], mp_hands.HAND_CONNECTIONS)
        
        frame = np.rot90(frame) 
        frame = pygame.surfarray.make_surface(frame)
        frame = pygame.transform.scale(frame, (320, 240))
        
        panel_x = (MAP_WIDTH - 320) // 2
        panel_y = map_bottom_y + 30
        
        pygame.draw.rect(screen, current_colors['CAMERA_FRAME'], 
                        (panel_x - 5, panel_y - 5, 330, 250), 3)
        screen.blit(frame, (panel_x, panel_y))
        
        dir_text = font.render(f"INPUT: {current_direction_name}", True, current_colors['TEXT'])
        text_rect = dir_text.get_rect(center=(MAP_WIDTH // 2, panel_y + 240 + 30))
        screen.blit(dir_text, text_rect)

        # ステータス表示
        if game_over:
            text = large_font.render("GAME OVER", True, (255, 0, 0))
            text_rect = text.get_rect(center=(MAP_WIDTH/2, SCREEN_HEIGHT/2))
            screen.blit(text, text_rect)
        elif game_clear:
            text = large_font.render("CLEAR!", True, (255, 255, 0))
            text_rect = text.get_rect(center=(MAP_WIDTH/2, SCREEN_HEIGHT/2))
            screen.blit(text, text_rect)
        elif not game_active:
            msg = large_font.render("PRESS START", True, (0, 255, 0))
            msg_rect = msg.get_rect(center=(MAP_WIDTH/2, SCREEN_HEIGHT/2))
            screen.blit(msg, msg_rect)

        pygame.display.flip()
        clock.tick(FPS)

    cap.release()
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()