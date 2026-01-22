import cv2
import mediapipe as mp
import math

class HandGestureRecognizer:
    def __init__(self):
        # MediaPipeの手の検出モデルの初期化
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,      # 動画モード
            max_num_hands=1,              # 検出する手の最大数
            min_detection_confidence=0.7, # 検出の信頼度閾値
            min_tracking_confidence=0.5   # 追跡の信頼度閾値
        )
        self.mp_drawing = mp.solutions.drawing_utils

    def calculate_distance(self, p1, p2):
        """2点間のユークリッド距離を計算する"""
        return math.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2)

    def is_finger_open(self, hand_landmarks, finger_name):
        """
        指が開いているか閉じているかを判定する
        指先(TIP)と指の付け根(PIP/MCP)の手首(WRIST)からの距離を比較して判定します。
        """
        # ランドマークのインデックス定義
        # 0: 手首
        wrist = hand_landmarks.landmark[0]
        
        # 指ごとのランドマークID (TIP: 指先, PIP: 第二関節, MCP: 付け根)
        finger_ids = {
            'THUMB':  {'TIP': 4,  'IP': 3,  'MCP': 2},  # 親指
            'INDEX':  {'TIP': 8,  'PIP': 6, 'MCP': 5},  # 人差し指
            'MIDDLE': {'TIP': 12, 'PIP': 10, 'MCP': 9}, # 中指
            'RING':   {'TIP': 16, 'PIP': 14, 'MCP': 13},# 薬指
            'PINKY':  {'TIP': 20, 'PIP': 18, 'MCP': 17} # 小指
        }

        ids = finger_ids[finger_name]
        tip = hand_landmarks.landmark[ids['TIP']]
        
        # 親指の場合の判定ロジック（親指は曲がる方向が他と異なるため）
        if finger_name == 'THUMB':
            # 親指のIP関節（第一関節）と小指の付け根(MCP)の距離などを比較する方法もあるが、
            # シンプルに「指先が付け根より手首から遠いか」と「ベクトル」で簡易判定
            
            # 親指の指先(4)と小指の付け根(17)の距離 と 親指の関節(2)と小指の付け根(17)の距離を比較
            # 開いている場合、指先の方が遠くなる傾向がある
            pinky_mcp = hand_landmarks.landmark[17]
            dist_tip_pinky = self.calculate_distance(tip, pinky_mcp)
            dist_mcp_pinky = self.calculate_distance(hand_landmarks.landmark[ids['MCP']], pinky_mcp)
            
            # 親指は個人差が大きいため、少し判定を緩くする
            return dist_tip_pinky > dist_mcp_pinky
        
        else:
            # 親指以外の4本指の判定ロジック
            # 指先(TIP)が手首(0)からの距離 と 第二関節(PIP)が手首(0)からの距離 を比較
            # 指先の方が遠ければ「開いている(伸びている)」とみなす
            pip = hand_landmarks.landmark[ids['PIP']]
            
            dist_tip_wrist = self.calculate_distance(tip, wrist)
            dist_pip_wrist = self.calculate_distance(pip, wrist)
            
            return dist_tip_wrist > dist_pip_wrist

    def classify_hand(self, hand_landmarks):
        """
        検出されたランドマークからジャンケンの手を判定する
        戻り値: "ROCK", "PAPER", "SCISSORS", "UNKNOWN"
        """
        fingers = ['THUMB', 'INDEX', 'MIDDLE', 'RING', 'PINKY']
        finger_states = {f: self.is_finger_open(hand_landmarks, f) for f in fingers}

        # デバッグ用：各指の状態を表示したい場合はコメントアウトを外す
        # print(finger_states)

        # 判定ロジック
        # True = 開いている, False = 閉じている

        # グー: 全ての指が閉じている
        # (親指の状態は個人差があるため、親指以外の4本が閉じていることを重視するケースもあるが、
        #  今回は定義通り「全て握っている」を確認する)
        if all(not finger_states[f] for f in fingers):
            return "ROCK" # グー
        
        # 親指が微妙な場合の「甘いグー」も許可する場合（オプション）
        # if not finger_states['INDEX'] and not finger_states['MIDDLE'] and \
        #    not finger_states['RING'] and not finger_states['PINKY']:
        #    return "ROCK"

        # パー: 5本すべて開いている
        if all(finger_states[f] for f in fingers):
            return "PAPER" # パー

        # チョキ: 人差し指と中指が開いている。親指・薬指・小指は閉じている。
        # (親指は開いていてもチョキとみなすバリエーションもあるが、定義通り判定する)
        if finger_states['INDEX'] and finger_states['MIDDLE']:
            if not finger_states['RING'] and not finger_states['PINKY']:
                # 親指の状態は問わない（普通のチョキも、親指を立てるチョキも許容）ことが多いが、
                # 定義通り「人差し指と中指だけ」を厳密にするなら親指もチェックする
                return "SCISSORS" # チョキ

        return "UNKNOWN"

    def process_frame(self, frame):
        # 左右反転（鏡のように表示するため）
        frame = cv2.flip(frame, 1)
        h, w, c = frame.shape

        # MediaPipe用に色変換 (BGR -> RGB)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # 骨格検出処理
        results = self.hands.process(rgb_frame)

        gesture_text = ""
        color = (255, 255, 255) # デフォルト白

        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                # 骨格の描画
                self.mp_drawing.draw_landmarks(
                    frame, 
                    hand_landmarks, 
                    self.mp_hands.HAND_CONNECTIONS,
                    self.mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=2, circle_radius=2),
                    self.mp_drawing.DrawingSpec(color=(0, 0, 255), thickness=2, circle_radius=2)
                )

                # ジャンケンの判定
                gesture = self.classify_hand(hand_landmarks)

                # 表示用テキストと色の設定
                if gesture == "ROCK":
                    gesture_text = "ROCK (Goo)"
                    color = (0, 0, 255) # 赤
                elif gesture == "PAPER":
                    gesture_text = "PAPER (Par)"
                    color = (0, 255, 0) # 緑
                elif gesture == "SCISSORS":
                    gesture_text = "SCISSORS (Choki)"
                    color = (255, 255, 0) # 水色/シアン
                else:
                    gesture_text = "UNKNOWN"
                    color = (200, 200, 200)

                # 画面上に判定結果を表示
                # OpenCVのputTextは日本語非対応のため英語で表示します
                cv2.putText(frame, gesture_text, (20, 80), 
                            cv2.FONT_HERSHEY_SIMPLEX, 2, color, 3, cv2.LINE_AA)

        return frame

def main():
    # カメラのキャプチャを開始 (0は標準カメラ)
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("カメラが見つかりませんでした。")
        return

    recognizer = HandGestureRecognizer()
    print("プログラムを開始します。'q'キーで終了します。")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("映像の取得に失敗しました。")
            break

        # フレーム処理と判定
        processed_frame = recognizer.process_frame(frame)

        # 画面表示
        cv2.imshow('Janken Hand Recognition', processed_frame)

        # 'q'キーで終了
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()