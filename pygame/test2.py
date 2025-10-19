# -*- coding: utf-8 -*-
import math
import sys
import pygame
from pygame.locals import *

# 画面サイズ
SCREEN = Rect(0, 0, 500, 600)

# 画像ファイルのパス
PADDLE_IMG_PATH = "image/paddle.png"
BLOCK_IMG_PATH = "image/backsnow.png"
BLOCKSTOP_IMG_PATH = "image/blockcatch.png"
BALL_IMG_PATH = "image/ball.png"

# バドルのスプライトクラス
class Paddle(pygame.sprite.Sprite):
    # コンストラクタ（初期化メソッド）
    def __init__(self, filename):
        pygame.sprite.Sprite.__init__(self, self.containers)
        self.image = pygame.image.load(filename).convert()
        self.rect = self.image.get_rect()
        self.rect.bottom = SCREEN.bottom - 20     # パドルのy座標

    def update(self):
        self.rect.centerx = pygame.mouse.get_pos()[0]  # マウスのx座標をパドルのx座標に
        self.rect.clamp_ip(SCREEN)                      # ゲーム画面内のみで移動

# ボールのスプライトクラス
class Ball(pygame.sprite.Sprite):
    # コンストラクタ（初期化メソッド）
    def __init__(self, filename, paddle, blocks, score, speed, angle_left, angle_right):
        pygame.sprite.Sprite.__init__(self, self.containers)
        self.image = pygame.image.load(filename).convert()
        self.rect = self.image.get_rect()
        self.dx = self.dy = 0  # ボールの速度
        self.paddle = paddle  # パドルへの参照
        self.blocks = blocks  # ブロックグループへの参照
        self.update = self.start # ゲーム開始状態に更新
        self.score = score
        self.hit = 0  # 連続でブロックを壊した回数
        self.speed = speed # ボールの初期速度
        self.angle_left = angle_left # パドルの反射方向(左端:135度）
        self.angle_right = angle_right # パドルの反射方向(右端:45度）
        self.is_game_over = False # ▼▼▼ Game Overフラグを追加 ▼▼▼

    # ゲーム開始状態（マウスを左クリック時するとボール射出）
    def start(self):
        self.rect.centerx = self.paddle.rect.centerx
        self.rect.bottom = self.paddle.rect.top
        if pygame.mouse.get_pressed()[0] == 1:
            self.dx = 0
            self.dy = -self.speed
            self.update = self.move

    # ボールの挙動
    def move(self):
        self.rect.centerx += self.dx
        self.rect.centery += self.dy
        if self.rect.left < SCREEN.left:
            self.rect.left = SCREEN.left
            self.dx = -self.dx
        if self.rect.right > SCREEN.right:
            self.rect.right = SCREEN.right
            self.dx = -self.dx
        if self.rect.top < SCREEN.top:
            self.rect.top = SCREEN.top
            self.dy = -self.dy
        if self.rect.colliderect(self.paddle.rect) and self.dy > 0:
            self.hit = 0
            (x1, y1) = (self.paddle.rect.left - self.rect.width, self.angle_left)
            (x2, y2) = (self.paddle.rect.right, self.angle_right)
            x = self.rect.left
            y = (float(y2-y1)/(x2-x1)) * (x - x1) + y1
            angle = math.radians(y)
            self.dx = self.speed * math.cos(angle)
            self.dy = -self.speed * math.sin(angle)

        # ▼▼▼ ボールを落としたら is_game_over フラグを True にする ▼▼▼
        if self.rect.top > SCREEN.bottom:
            self.is_game_over = True

        blocks_collided = pygame.sprite.spritecollide(self, self.blocks, True)
        if blocks_collided:
            oldrect = self.rect
            for block in blocks_collided:
                if oldrect.left < block.rect.left and oldrect.right < block.rect.right:
                    self.rect.right = block.rect.left
                    self.dx = -self.dx
                if block.rect.left < oldrect.left and block.rect.right < oldrect.right:
                    self.rect.left = block.rect.right
                    self.dx = -self.dx
                if oldrect.top < block.rect.top and oldrect.bottom < block.rect.bottom:
                    self.rect.bottom = block.rect.top
                    self.dy = -self.dy
                if block.rect.top < oldrect.top and block.rect.bottom < oldrect.bottom:
                    self.rect.top = block.rect.bottom
                    self.dy = -self.dy
                self.hit += 1
                self.score.add_score(self.hit * 10)

# ブロック
class Block(pygame.sprite.Sprite):
    def __init__(self, filename, x, y):
        pygame.sprite.Sprite.__init__(self, self.containers)
        self.image = pygame.image.load(filename).convert()
        self.rect = self.image.get_rect()
        self.rect.left = SCREEN.left + x * self.rect.width
        self.rect.top = SCREEN.top + y * self.rect.height

# スコア
class Score():
    def __init__(self, x, y):
        self.sysfont = pygame.font.SysFont(None, 20)
        self.score = 0
        (self.x, self.y) = (x, y)
    def draw(self, screen):
        img = self.sysfont.render("SCORE:" + str(self.score), True, (255,255,250))
        screen.blit(img, (self.x, self.y))
    def add_score(self, x):
        self.score += x
    def set_score(self, score):
        self.score = score

def main():
    pygame.init()
    screen = pygame.display.set_mode(SCREEN.size)
    
    # スプライトグループの準備
    group = pygame.sprite.RenderUpdates()
    blocks = pygame.sprite.Group()
    Paddle.containers = group
    Ball.containers = group
    Block.containers = group, blocks

    # --- ゲーム要素の初期作成 ---
    paddle = Paddle(PADDLE_IMG_PATH)
    score = Score(10, 10)

    # ▼▼▼ ブロックの作成(10*10)に変更 ▼▼▼
    # マージンを考慮して配置
    block_width = pygame.image.load(BLOCK_IMG_PATH).get_width()
    block_height = pygame.image.load(BLOCK_IMG_PATH).get_height()
    for x in range(10):
        for y in range(10):
            # 画面サイズとブロック数から配置位置を計算し、中央に寄せる
            px = 50 + x * (block_width + 5)
            py = 50 + y * (block_height + 5)
            Block(BLOCK_IMG_PATH, px / block_width, py / block_height)
    
    ball = Ball(BALL_IMG_PATH, paddle, blocks, score, 7, 135, 45) # ボールのスピードを少し上げた
    
    clock = pygame.time.Clock()

    # --- ゲームオーバーとクリア画面用のUI準備 ---
    game_over_font = pygame.font.SysFont(None, 80)
    clear_font = pygame.font.SysFont(None, 100)
    retry_font = pygame.font.SysFont(None, 50)

    # --- ゲームの状態を管理する変数 ---
    game_state = "playing" # "playing", "game_over", "clear"

    running = True
    while running:
        clock.tick(60)
        screen.fill((0, 20, 0))

        # --- イベント処理 ---
        for event in pygame.event.get():
            if event.type == QUIT:
                running = False
            if event.type == KEYDOWN and event.key == K_ESCAPE:
                running = False
            
            # ▼▼▼ リトライボタンのクリック処理 ▼▼▼
            if event.type == MOUSEBUTTONDOWN and game_state == "game_over":
                # retry_button_rectは後で定義
                if retry_button_rect.collidepoint(event.pos):
                    # --- ゲームのリセット処理 ---
                    game_state = "playing"
                    # 全てのスプライトを削除
                    group.empty()
                    blocks.empty()
                    # スプライトを再作成
                    paddle = Paddle(PADDLE_IMG_PATH)
                    score.set_score(0)
                    for x in range(10):
                        for y in range(10):
                            px = 50 + x * (block_width + 5)
                            py = 50 + y * (block_height + 5)
                            Block(BLOCK_IMG_PATH, px/block_width, py/block_height)
                    ball = Ball(BALL_IMG_PATH, paddle, blocks, score, 7, 135, 45)

        # --- ゲームの状態に応じた処理 ---
        if game_state == "playing":
            group.update()
            group.draw(screen)
            score.draw(screen)

            # ボールが落ちたらゲームオーバーに移行
            if ball.is_game_over:
                game_state = "game_over"
            
            # ブロックがなくなったらクリアに移行
            if len(blocks) == 0:
                game_state = "clear"

        elif game_state == "game_over":
            # --- ゲームオーバー画面の描画 ---
            # "Gameover"の文字
            game_over_text = game_over_font.render("Game Over", True, (255, 0, 0))
            text_rect = game_over_text.get_rect(center=(SCREEN.centerx, SCREEN.centery - 50))
            screen.blit(game_over_text, text_rect)
            
            # スコア表示
            final_score_text = score.sysfont.render("SCORE: " + str(score.score), True, (255, 255, 255))
            score_rect = final_score_text.get_rect(center=(SCREEN.centerx, SCREEN.centery + 20))
            screen.blit(final_score_text, score_rect)

            # リトライボタン
            retry_text = retry_font.render("Retry", True, (0, 0, 0))
            retry_button_rect = pygame.Rect(SCREEN.centerx - 70, SCREEN.centery + 60, 140, 50)
            pygame.draw.rect(screen, (255, 255, 255), retry_button_rect)
            retry_text_rect = retry_text.get_rect(center=retry_button_rect.center)
            screen.blit(retry_text, retry_text_rect)

        elif game_state == "clear":
            # --- クリア画面の描画 ---
            clear_text = clear_font.render("Nice try", True, (255, 255, 0))
            text_rect = clear_text.get_rect(center=SCREEN.center)
            screen.blit(clear_text, text_rect)
        
        pygame.display.update()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()