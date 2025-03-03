import os
import numpy as np
from PIL import Image
import tensorflow as tf
from tensorflow.keras import layers, models
from sklearn.model_selection import train_test_split

# Các ký tự có thể xuất hiện trong captcha (chỉ chữ cái)
CHARACTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
CHAR_TO_INT = {char: i for i, char in enumerate(CHARACTERS)}
INT_TO_CHAR = {i: char for i, char in enumerate(CHARACTERS)}
MAX_LENGTH = 6  # Độ dài tối đa của captcha

# Thêm class GetItem để xử lý custom layer
class GetItem(layers.Layer):
    def __init__(self, index, **kwargs):
        super(GetItem, self).__init__(**kwargs)
        self.index = index

    def call(self, inputs):
        return inputs[:, self.index, :]

    def get_config(self):
        config = super(GetItem, self).get_config()
        config.update({'index': self.index})
        return config

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
        char_output = GetItem(i)(x)
        output = layers.Dense(len(CHARACTERS), activation='softmax', name=f'char_{i}')(char_output)
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

    # Sửa phần compile để có metrics cho mỗi output
    model.compile(
        optimizer='adam',
        loss=['categorical_crossentropy'] * MAX_LENGTH,
        metrics=[['accuracy'] for _ in range(MAX_LENGTH)]  # Metrics cho mỗi output
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

    # Lưu model với định dạng mới
    print("Lưu model...")
    if not os.path.exists('output'):
        os.makedirs('output')
    model.save('output/captcha_model.keras')  # Thay đổi từ .h5 sang .keras

    return history

def test_model():
    print("Kiểm tra model...")
    # Tải model với custom objects
    custom_objects = {'GetItem': GetItem}
    model = models.load_model('output/captcha_model.keras', custom_objects=custom_objects)

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

def evaluate_model():
    print("\nĐánh giá model trên toàn bộ tập test...")
    custom_objects = {'GetItem': GetItem}
    model = models.load_model('output/captcha_model.keras', custom_objects=custom_objects)

    # Tải tất cả dữ liệu test
    test_images = []
    test_labels = []

    with open("training_captchas/labels.txt", "r") as f:
        for line in f:
            img_name, label = line.strip().split('\t')
            img_path = os.path.join("training_captchas", img_name)

            img = Image.open(img_path).convert('L')
            img = img.resize((200, 50))
            img_array = np.array(img) / 255.0
            test_images.append(img_array)
            test_labels.append(label)

    test_images = np.array(test_images).reshape(-1, 50, 200, 1)
    predictions = model.predict(test_images)

    correct = 0
    total = len(test_labels)

    for i, pred in enumerate(zip(*predictions)):
        pred_text = ''
        for p in pred:
            pred_text += INT_TO_CHAR[np.argmax(p)]

        if pred_text == test_labels[i]:
            correct += 1

    accuracy = correct / total
    print(f"\nĐộ chính xác tổng thể: {accuracy:.2%}")
    print(f"Số lượng dự đoán đúng: {correct}/{total}")

def analyze_data():
    """Phân tích dữ liệu training để đảm bảo chất lượng"""
    print("\nPhân tích dữ liệu training...")

    with open("training_captchas/labels.txt", "r") as f:
        labels = [line.strip().split('\t')[1] for line in f]

    # Thống kê độ dài
    lengths = [len(label) for label in labels]
    print(f"Số lượng mẫu: {len(labels)}")
    print(f"Độ dài min: {min(lengths)}, max: {max(lengths)}")

    # Thống kê tần suất ký tự
    char_freq = {}
    for label in labels:
        for char in label:
            char_freq[char] = char_freq.get(char, 0) + 1

    print("\nTần suất các ký tự:")
    for char, freq in sorted(char_freq.items()):
        print(f"{char}: {freq}")

    # Kiểm tra ảnh
    print("\nKiểm tra ảnh...")
    invalid_images = []
    for line in open("training_captchas/labels.txt", "r"):
        img_name = line.strip().split('\t')[0]
        img_path = os.path.join("training_captchas", img_name)
        try:
            img = Image.open(img_path).convert('L')
            img_array = np.array(img)
            if img_array.std() < 20:  # Kiểm tra độ tương phản
                invalid_images.append(f"{img_name} (low contrast)")
        except Exception as e:
            invalid_images.append(f"{img_name} (error: {str(e)})")

    if invalid_images:
        print("\nẢnh có vấn đề:")
        for img in invalid_images:
            print(img)

def create_model_v2():
    """Phiên bản đơn giản hóa của model"""
    inputs = layers.Input(shape=(50, 200, 1))

    # Simplified CNN
    x = layers.Conv2D(32, (3, 3), activation='relu', padding='same')(inputs)
    x = layers.MaxPooling2D((2, 2))(x)
    x = layers.Conv2D(64, (3, 3), activation='relu', padding='same')(x)
    x = layers.MaxPooling2D((2, 2))(x)

    # Global features
    x = layers.Flatten()(x)
    x = layers.Dense(512, activation='relu')(x)
    x = layers.Dropout(0.5)(x)

    # Separate dense layer for each character
    outputs = []
    for i in range(MAX_LENGTH):
        output = layers.Dense(len(CHARACTERS), activation='softmax', name=f'char_{i}')(x)
        outputs.append(output)

    model = models.Model(inputs=inputs, outputs=outputs)
    return model

def train_v2():
    """Phiên bản cải tiến của hàm training"""
    # Tải và phân tích dữ liệu
    analyze_data()

    # Tải dữ liệu
    X, y = load_data()
    print(f"\nĐã tải {len(X)} mẫu dữ liệu")

    # Chia tập train/val
    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)
    X_train = X_train.reshape(-1, 50, 200, 1)
    X_val = X_val.reshape(-1, 50, 200, 1)

    # Tạo model đơn giản hơn
    model = create_model_v2()

    # Tách labels
    y_train_split = [y_train[:, i] for i in range(MAX_LENGTH)]
    y_val_split = [y_val[:, i] for i in range(MAX_LENGTH)]

    # Compile với metrics cho từng output
    optimizer = tf.keras.optimizers.Adam(learning_rate=0.0001)
    model.compile(
        optimizer=optimizer,
        loss=['categorical_crossentropy'] * MAX_LENGTH,
        metrics=[['accuracy'] for _ in range(MAX_LENGTH)]  # Metrics riêng cho từng output
    )

    # Training với batch size nhỏ và nhiều epochs
    print("\nBắt đầu training...")
    history = model.fit(
        X_train,
        y_train_split,
        validation_data=(X_val, y_val_split),
        epochs=100,
        batch_size=8,
        callbacks=[
            tf.keras.callbacks.EarlyStopping(
                monitor='val_loss',
                patience=15,
                restore_best_weights=True
            ),
            tf.keras.callbacks.ReduceLROnPlateau(
                monitor='val_loss',
                factor=0.5,
                patience=5
            )
        ]
    )

    # Lưu model
    model.save('output/captcha_model.keras')
    return history

if __name__ == "__main__":
    print("=== Bắt đầu quá trình training ===")
    history = train_v2()
    test_model()
    evaluate_model()
