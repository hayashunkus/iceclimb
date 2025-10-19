# -*- coding: utf-8 -*-
import math
import sys
import pygame
from pygame.locals import *
import random

# 画面サイズ
SCREEN = Rect(0, 0, 450, 600)

# 画像ファイルのパス
PADDLE_IMG_PATH = "image/paddle.png"
BLOCK_IMG_PATH = "image/backsnow.png"      # 壊せるブロック (体力1)
BLOCKSTOP_IMG_PATH = "image/blockcatch.png" # 硬いブロック (体力2)
BALL_IMG_PATH = "image/ball.png"

# バドルのスプライトクラス
class Paddle(pygame.sprite.Sprite):
    def __init__(self, filename, *groups):
        pygame.sprite.Sprite.__init__(self, *groups)
        self.image = pygame.image.load(filename).convert()
        self.rect = self.image.get_rect()
        self.rect.bottom = SCREEN.bottom - 20

    def update(self):
        self.rect.centerx = pygame.mouse.get_pos()[0]
        self.rect.clamp_ip(SCREEN)

# ボールのスプライトクラス
class Ball(pygame.sprite.Sprite):
    # ▼▼▼ blocksグループを1つに統合 ▼▼▼
    def __init__(self, filename, paddle, blocks, score, speed, angle_left, angle_right, *groups):
        pygame.sprite.Sprite.__init__(self, *groups)
        self.image = pygame.image.load(filename).convert()
        self.rect = self.image.get_rect()
        self.dx = self.dy = 0
        self.paddle = paddle
        self.blocks = blocks # すべてのブロックが入ったグループ
        self.update = self.start
        self.score = score
        self.hit = 0
        self.speed = speed
        self.angle_left = angle_left
        self.angle_right = angle_right
        self.is_game_over = False

    def start(self):
        self.rect.centerx = self.paddle.rect.centerx
        self.rect.bottom = self.paddle.rect.top
        if pygame.mouse.get_pressed()[0] == 1:
            self.dx = 0
            self.dy = -self.speed
            self.update = self.move

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

        if self.rect.top > SCREEN.bottom:
            self.is_game_over = True

        # ▼▼▼▼▼ 衝突判定ロジックを体力制に変更 ▼▼▼▼▼
        # 衝突したブロックのリストを取得（ブロックはまだ消さない）
        collided_blocks = pygame.sprite.spritecollide(self, self.blocks, False)
        
        if collided_blocks:
            # 最初に衝突したブロックを取得
            block = collided_blocks[0]
            
            # ブロックのhitメソッドを呼び出し、破壊されたかどうかを受け取る
            destroyed = block.hit()
            
            # ブロックが破壊された場合のみスコアを加算
            if destroyed:
                self.hit += 1
                self.score.add_score(self.hit * 10)

            # ボールの反射処理
            oldrect = self.rect
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
        # ▲▲▲▲▲ 衝突判定ロジックの変更ここまで ▲▲▲▲▲

# ブロック
class Block(pygame.sprite.Sprite):
    # ▼▼▼ 体力(health)をコンストラクタで受け取るように変更 ▼▼▼
    def __init__(self, filename, x, y, health, *groups):
        pygame.sprite.Sprite.__init__(self, *groups)
        self.image = pygame.image.load(filename).convert()
        self.rect = self.image.get_rect()
        self.rect.left = x
        self.rect.top = y
        self.health = health # 体力を設定

    # ▼▼▼ ボールが当たった時の処理を追加 ▼▼▼
    def hit(self):
        """ブロックの体力を1減らし、体力が0になったら自身を消去する"""
        self.health -= 1
        if self.health <= 0:
            self.kill() # スプライトグループから自身を削除
            return True # 破壊されたことを通知
        return False # まだ破壊されていないことを通知

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
    
    # --- スプライトグループの準備 ---
    all_sprites = pygame.sprite.RenderUpdates()
    all_blocks = pygame.sprite.Group()  # ▼▼▼ すべてのブロックを管理するグループ ▼▼▼

    # --- ゲーム要素の初期作成関数 ---
    def setup_game():
        all_sprites.empty()
        all_blocks.empty()
        
        paddle = Paddle(PADDLE_IMG_PATH, all_sprites)
        
        block_width = pygame.image.load(BLOCK_IMG_PATH).get_width()
        block_height = pygame.image.load(BLOCK_IMG_PATH).get_height()
        for y in range(10):
            for x in range(10):
                px = 25 + x * (block_width + 5)
                py = 50 + y * (block_height + 5)
                
                # ▼▼▼ 確率に応じて体力1か体力2のブロックを生成 ▼▼▼
                if random.random() < 0.3: 
                    # 体力2のブロック
                    Block(BLOCKSTOP_IMG_PATH, px, py, 2, all_sprites, all_blocks)
                else:
                    # 体力1のブロック
                    Block(BLOCK_IMG_PATH, px, py, 1, all_sprites, all_blocks)
        
        score = Score(10, 10)
        # ▼▼▼ Ballにはall_blocksグループを渡す ▼▼▼
        ball = Ball(BALL_IMG_PATH, paddle, all_blocks, score, 7, 135, 45, all_sprites)
        
        return paddle, score, ball

    paddle, score, ball = setup_game()
    clock = pygame.time.Clock()

    game_over_font = pygame.font.SysFont(None, 80)
    clear_font = pygame.font.SysFont(None, 100)
    retry_font = pygame.font.SysFont(None, 50)

    game_state = "playing"
    running = True
    while running:
        clock.tick(60)
        screen.fill((0, 20, 0))

        for event in pygame.event.get():
            if event.type == QUIT:
                running = False
            if event.type == KEYDOWN and event.key == K_ESCAPE:
                running = False
            
            if event.type == MOUSEBUTTONDOWN and game_state == "game_over":
                if retry_button_rect.collidepoint(event.pos):
                    paddle, score, ball = setup_game()
                    game_state = "playing"

        if game_state == "playing":
            all_sprites.update()
            all_sprites.draw(screen)
            score.draw(screen)

            if ball.is_game_over:
                game_state = "game_over"
            
            # ▼▼▼ クリア条件を「すべてのブロックが0」に変更 ▼▼▼
            if len(all_blocks) == 0:
                game_state = "clear"

        elif game_state == "game_over":
            game_over_text = game_over_font.render("Game Over", True, (255, 0, 0))
            text_rect = game_over_text.get_rect(center=(SCREEN.centerx, SCREEN.centery - 50))
            screen.blit(game_over_text, text_rect)
            
            final_score_text = score.sysfont.render("SCORE: " + str(score.score), True, (255, 255, 255))
            score_rect = final_score_text.get_rect(center=(SCREEN.centerx, SCREEN.centery + 20))
            screen.blit(final_score_text, score_rect)

            retry_text = retry_font.render("Retry", True, (0, 0, 0))
            retry_button_rect = pygame.Rect(SCREEN.centerx - 70, SCREEN.centery + 60, 140, 50)
            pygame.draw.rect(screen, (255, 255, 255), retry_button_rect)
            retry_text_rect = retry_text.get_rect(center=retry_button_rect.center)
            screen.blit(retry_text, retry_text_rect)

        elif game_state == "clear":
            clear_text = clear_font.render("Nice try", True, (255, 255, 0))
            text_rect = clear_text.get_rect(center=SCREEN.center)
            screen.blit(clear_text, text_rect)
        
        pygame.display.update()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()

