from pypylon import pylon
import cv2
import numpy as np
import snap7
import time

# Conectando à câmera
camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())

EXTERNAL_TRIGGER = True

# Tentando conectar ao CLP com tratamento de exceção
plc = snap7.client.Client()
try:
    plc.connect('172.16.x.x', 0, 2)  # 1: '172.16.x.x' / 2: '172.16.x.x'
    if not plc.get_connected():
        raise ConnectionError("CLP não está conectado.")
except Exception as e:
    print("Erro ao conectar ao CLP")
    print("Verifique o endereço IP, a conexão de rede ou se o CLP está ligado.")
    exit(1)

aux = True
x = True

print("Aguardando Bobina 1")

while x:
    try:
        reading = plc.db_read(40, 42, 1)
    except Exception as e:
        print("Erro ao ler dados do CLP")
        x = False
        continue

    if 1 in reading:
        aux = True

    if aux:
        try:
            camera.Open()
            camera.Width.Value = camera.Width.Max
            camera.Height.Value = camera.Height.Max
            camera.TriggerSource.Value = "Software"
            camera.TriggerMode.Value = "On"
        except Exception as e:
            print(f"Erro ao configurar a câmera")
            break

        # Valores constantes
        num_images = 4
        screen_width, screen_height = 1366, 768
        resized_images = []
        current_image_index = 0
        combined_image = np.zeros((screen_height, screen_width, 3), dtype=np.uint8)

        # Conversor de imagem
        converter = pylon.ImageFormatConverter()
        converter.OutputPixelFormat = pylon.PixelType_BGR8packed
        converter.OutputBitAlignment = pylon.OutputBitAlignment_MsbAligned

        camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)

        last_bit_state = False

        while camera.IsGrabbing():
            cv2.imshow('Combined Images', combined_image)
            key = cv2.waitKey(1)
            if key == 27:
                camera.StopGrabbing()
                break

            try:
                reading2 = plc.db_read(40, 36, 1)
                bit_state = 1 in reading2
            except Exception as e:
                print("Erro ao ler sinal do CLP")
                x = False
                continue

            if bit_state and not last_bit_state:
                camera.ExecuteSoftwareTrigger()

                if not camera.GetGrabResultWaitObject().Wait(5000):
                    continue

                try:
                    with camera.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException) as grabResult:
                        assert grabResult.GrabSucceeded()
                        image = converter.Convert(grabResult)
                        img = image.GetArray()
                except Exception as e:
                    print(f"Erro ao capturar imagem")
                    continue

                if len(resized_images) < num_images:
                    resized_images.append(img.copy())
                else:
                    resized_images[current_image_index] = img.copy()
                    current_image_index = (current_image_index + 1) % num_images

                for i in range(len(resized_images)):
                    h, w, _ = resized_images[i].shape
                    h_ratio = screen_height // 2
                    w_ratio = screen_width // 2

                    if i == 0:
                        row, col = 1, 1
                    elif i == 1:
                        row, col = 0, 1
                    elif i == 2:
                        row, col = 1, 0
                    elif i == 3:
                        row, col = 0, 0

                    resized_images[i] = cv2.resize(resized_images[i], (w_ratio, h_ratio))
                    combined_image[row * h_ratio:(row + 1) * h_ratio, col * w_ratio:(col + 1) * w_ratio, :] = resized_images[i]

            last_bit_state = bit_state

        cv2.waitKey(0)
        cv2.destroyAllWindows()
        camera.Close()
        break
