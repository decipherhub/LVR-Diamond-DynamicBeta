import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import numpy as np
from numpy import random as rn
import matplotlib.pyplot as plt
from PPO import ScaleToRange


# PyTorch 모델 정의
class TorchModel(nn.Module):
    def __init__(self):
        super(TorchModel, self).__init__()
        self.fc1 = nn.Linear(1, 10)
        self.fc2 = nn.Linear(10, 10)
        self.fc3 = nn.Linear(10, 10)
        self.fc4 = nn.Linear(10, 10)
        self.fc5 = nn.Linear(10, 1)

    def forward(self, x):
        x = torch.relu(self.fc1(x))
        x = torch.relu(self.fc2(x))
        x = torch.relu(self.fc3(x))
        x = torch.relu(self.fc4(x))
        x = self.fc5(x)
        return x


def findPctToReAdd(volatility):
    a = 2.5848651656619483e-35
    b = 0.00031792625279230245
    c = 0.0025417934558708715

    return a + b / (volatility + c)


# 데이터 준비
x = np.arange(0, 1, 0.001)
y = np.array([findPctToReAdd(volatility) for volatility in x])
# x = np.linspace(-10, 10, 100)
# y = 3 * np.sin(x) * np.cos(x) * (6 * x**2 + 3 * x**3 + x**1) * np.tan(x)

pre_trained_model = nn.Sequential(
    nn.Linear(1, 64),
    nn.ReLU(),
    nn.Linear(64, 128),
    nn.ReLU(),
    nn.Linear(128, 128),
    nn.ReLU(),
    nn.Linear(128, 128),
    nn.ReLU(),
    nn.Linear(128, 64),
    nn.ReLU(),
    nn.Linear(64, 1),
    ScaleToRange(0, 1),
)


def pretrain():
    # 모델, 손실 함수, 옵티마이저 설정
    # model = PreTrainedActor()

    criterion = nn.MSELoss()
    # optimizer = optim.RMSprop(model.parameters(), lr=0.001, alpha=0.9, eps=1e-08)
    optimizer = optim.Adam(pre_trained_model.parameters(), lr=0.001)

    # 학습 과정
    for epoch in range(3000):
        optimizer.zero_grad()

        # numpy 배열을 PyTorch 텐서로 변환
        inputs = torch.from_numpy(x).float().view(-1, 1)
        targets = torch.from_numpy(y).float().view(-1, 1)

        # outputs = model(inputs)
        outputs = pre_trained_model(inputs)
        loss = criterion(outputs, targets)

        loss.backward()
        optimizer.step()

        if epoch % 100 == 0:
            print(f"Epoch {epoch+1}/3000, Loss: {loss.item()}")

    return pre_trained_model


if __name__ == "__main__":
    model = pretrain()

    # 예측 및 시각화
    with torch.no_grad():
        predicted = model(torch.from_numpy(x).float().view(-1, 1)).numpy()
    plt.plot(x, y, label="Original")
    plt.plot(x, predicted, label="Predicted")
    plt.legend()
    plt.show()

    # import matplotlib.pyplot as plt
    # from keras.models import Sequential
    # from keras.layers import Dense
    # from tensorflow.keras import optimizers

    # model = Sequential()
    # model.add(Dense(10, input_shape=(1,), activation="relu"))
    # model.add(Dense(10, input_shape=(1,), activation="relu"))
    # model.add(Dense(10, input_shape=(1,), activation="relu"))
    # model.add(Dense(10, input_shape=(1,), activation="relu"))
    # model.add(Dense(1, activation="linear"))
    # rms = optimizers.RMSprop(lr=0.001, rho=0.9, epsilon=1e-08, decay=0.0)
    # model.compile(loss="mean_squared_error", optimizer=rms, metrics=["accuracy"])
    # # dont print training process
    # model.fit(np.array(x), np.array(y), epochs=3000, verbose=0)

    # prediction = model.predict(np.array(x))
    # plt.plot(x, prediction)
    # plt.show()
