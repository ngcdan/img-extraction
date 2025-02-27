import os
import numpy as np
from PIL import Image
import tensorflow as tf
from tensorflow.keras import layers, models
from sklearn.model_selection import train_test_split

# Các ký tự có thể xuất hiện trong captcha
CHARACTERS = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
CHAR_TO_INT = {char: i for i, char in enumerate(CHARACTERS)}
INT_TO_CHAR = {i: char for i, char in enumerate(CHARACTERS)}
MAX_LENGTH = 6  # Độ dài tối đa của captcha

def load_data():
    print("Đang tải dữ liệu...")
    images = []
    labels = []

    # Đọc file labels.txt
    with open("training_captchas/labels.txt", "r") as f:
        for line in f:
            img_name, label = line.strip().split('\t')
            img_path = os.path.join("training_captchas", img_name)

            # Đọc và xử lý ảnh
            img = Image.open(img_path).convert('L')  # Chuyển sang ảnh xám
            img = img.resize((200, 50))  # Resize về kích thước cố định
            img_array = np.array(img) / 255.0  # Normalize
            images.append(img_array)

            # Chuyển label thành one-hot encoding
            label_array = np.zeros((MAX_LENGTH, len(CHARACTERS)))
            for i, char in enumerate(label):
                if i < MAX_LENGTH:
                    label_array[i][CHAR_TO_INT[char]] = 1
            labels.append(label_array)

    return np.array(images), np.array(labels)

def create_model():
    # Input layer
    inputs = layers.Input(shape=(50, 200, 1))

    # CNN layers
    x = layers.Conv2D(32, (3, 3), activation='relu', padding='same')(inputs)
    x = layers.MaxPooling2D((2, 2))(x)
    x = layers.Conv2D(64, (3, 3), activation='relu', padding='same')(x)
    x = layers.MaxPooling2D((2, 2))(x)
    x = layers.Conv2D(128, (3, 3), activation='relu', padding='same')(x)
    x = layers.MaxPooling2D((2, 2))(x)

    # Reshape for sequence processing
    x = layers.Reshape((-1, 128))(x)

    # RNN layers
    x = layers.Bidirectional(layers.LSTM(128, return_sequences=True))(x)
    x = layers.Dropout(0.2)(x)

    # Output layers - một layer cho mỗi ký tự
    outputs = []
    for i in range(MAX_LENGTH):
        output = layers.Dense(len(CHARACTERS), activation='softmax', name=f'char_{i}')(x[:, i, :])
        outputs.append(output)

    model = models.Model(inputs=inputs, outputs=outputs)
    return model

def train():
    # Tải dữ liệu
    X, y = load_data()
    print(f"Đã tải {len(X)} mẫu dữ liệu")

    # Chia training/validation
    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)

    # Reshape input cho phù hợp với model
    X_train = X_train.reshape(-1, 50, 200, 1)
    X_val = X_val.reshape(-1, 50, 200, 1)

    # Tạo và biên dịch model
    model = create_model()

    # Tách y thành các outputs riêng biệt
    y_train_split = [y_train[:, i] for i in range(MAX_LENGTH)]
    y_val_split = [y_val[:, i] for i in range(MAX_LENGTH)]

    model.compile(
        optimizer='adam',
        loss=['categorical_crossentropy'] * MAX_LENGTH,
        metrics=['accuracy']
    )

    # Training
    print("Bắt đầu training...")
    history = model.fit(
        X_train,
        y_train_split,
        validation_data=(X_val, y_val_split),
        epochs=50,
        batch_size=32
    )

    # Lưu model
    print("Lưu model...")
    if not os.path.exists('output'):
        os.makedirs('output')
    model.save('output/captcha_model.h5')

    return history

def test_model():
    print("Kiểm tra model...")
    model = models.load_model('output/captcha_model.h5')

    # Test với một số ảnh
    test_images = []
    test_labels = []

    with open("training_captchas/labels.txt", "r") as f:
        for i, line in enumerate(f):
            if i >= 5:  # Test 5 ảnh đầu
                break
            img_name, label = line.strip().split('\t')
            img_path = os.path.join("training_captchas", img_name)

            # Xử lý ảnh
            img = Image.open(img_path).convert('L')
            img = img.resize((200, 50))
            img_array = np.array(img) / 255.0
            test_images.append(img_array)
            test_labels.append(label)

    test_images = np.array(test_images).reshape(-1, 50, 200, 1)
    predictions = model.predict(test_images)

    # Chuyển predictions thành text
    for i, pred in enumerate(zip(*predictions)):
        pred_text = ''
        for p in pred:
            pred_text += INT_TO_CHAR[np.argmax(p)]
        print(f"Ảnh {i + 1}:")
        print(f"Thực tế: {test_labels[i]}")
        print(f"Dự đoán: {pred_text}")
        print("---")

if __name__ == "__main__":
    print("=== Bắt đầu quá trình training ===")

    # Training
    history = train()

    # Test model
    test_model()