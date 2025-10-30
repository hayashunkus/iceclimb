import pygame
pygame.init()

# 画面設定
WIDTH, HEIGHT = 800, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("ゲームのホーム画面")
clock = pygame.time.Clock()

# --- 色の定義 ---
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREEN = (0, 150, 0)
BLUE = (0, 0, 150)
RED = (150, 0, 0)

# --- ステート管理 ---
current_state = "home" # 最初の画面を 'home' に設定

# --- ボタンの定義（ホーム画面用） ---
# pygame.Rect(x座標, y座標, 幅, 高さ) でボタンの領域を定義
play_button = pygame.Rect(300, 200, 200, 50)
how_to_play_button = pygame.Rect(300, 300, 200, 50)
menu_button = pygame.Rect(300, 400, 200, 50)

# フォントの準備
try:
    # 日本語を表示するために、システムに存在するフォントを指定
    font = pygame.font.SysFont("Meiryo", 40) # Windowsの場合
except:
    try:
        font = pygame.font.SysFont("Hiragino Sans", 40) # macOSの場合
    except:
        font = pygame.font.Font(None, 40) # デフォルトフォント

def draw_text(text, rect, text_color, bg_color):
    """ボタンを描画するヘルパー関数"""
    pygame.draw.rect(screen, bg_color, rect)
    text_surface = font.render(text, True, text_color)
    text_rect = text_surface.get_rect(center=rect.center)
    screen.blit(text_surface, text_rect)

# --- メインループ ---
running = True
while running:
    
    # イベント処理
    mouse_pos = pygame.mouse.get_pos()
    
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        
        # --- クリック処理 ---
        if event.type == pygame.MOUSEBUTTONDOWN:
            # ホーム画面でのクリック処理
            if current_state == "home":
                if play_button.collidepoint(mouse_pos):
                    print("プレイボタンが押されました")
                    current_state = "play" # ステートを "play" に変更
                
                elif how_to_play_button.collidepoint(mouse_pos):
                    print("遊び方ボタンが押されました")
                    current_state = "how_to_play" # ステートを "how_to_play" に変更
                
                elif menu_button.collidepoint(mouse_pos):
                    print("メニューボタンが押されました")
                    current_state = "menu" # ステートを "menu" に変更
            
            # 他の画面で「ホームに戻る」処理（例: どこかをクリックしたら戻る）
            elif current_state == "play" or current_state == "how_to_play" or current_state == "menu":
                # ここに「戻るボタン」の判定などを追加できます
                # 例として、画面クリックでホームに戻る
                current_state = "home"
                print("ホームに戻ります")


    # --- 画面描画（ステートごと）---
    screen.fill(WHITE) # 背景を白で塗りつぶし

    if current_state == "home":
        # ホーム画面の描画
        draw_text("プレイ", play_button, WHITE, GREEN)
        draw_text("遊び方", how_to_play_button, WHITE, BLUE)
        draw_text("メニュー", menu_button, WHITE, RED)

    elif current_state == "play":
        # プレイ画面の描画処理
        play_text = font.render("プレイ画面です", True, BLACK)
        screen.blit(play_text, (WIDTH // 2 - play_text.get_width() // 2, HEIGHT // 2))
        # ここにゲーム本体のロジックを描く

    elif current_state == "how_to_play":
        # 遊び方画面の描画処理
        how_to_text = font.render("遊び方画面です", True, BLACK)
        screen.blit(how_to_text, (WIDTH // 2 - how_to_text.get_width() // 2, HEIGHT // 2))
        # ここに遊び方の説明を描く

    elif current_state == "menu":
        # メニュー画面の描画処理
        menu_text = font.render("ミニゲームメニューです", True, BLACK)
        screen.blit(menu_text, (WIDTH // 2 - menu_text.get_width() // 2, HEIGHT // 2))
        # ここにミニゲーム選択肢を描く

    # 画面更新
    pygame.display.flip()
    clock.tick(60)

pygame.quit()