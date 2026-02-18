"""
MascoteApp - Mantenha-se ativo no Teams

Este aplicativo simula atividade no computador para evitar status "ausente" em aplicativos como o Microsoft Teams.
Funcionalidades:
- Mascote animado (GIF) exibido na interface.
- Movimenta o mouse e pressiona teclas periodicamente.
- Permite configurar o intervalo entre ações.
- Emite som opcional a cada ciclo.
- Registra cada ciclo em um arquivo de log (cycle_log.txt).
- Interface gráfica fixa, com ícone personalizado.

Requisitos:
- Python 3.x
- Bibliotecas: tkinter, pillow, pyautogui

Autor: Christian Vladimir Uhdre Mulato
Data: Campo Largo, segunda-feira, 29 de Setembro de 2025.
"""

import tkinter as tk
from tkinter import messagebox
import threading
import time
import pyautogui
import subprocess
import datetime
import os
import random
from PIL import Image, ImageTk
import psutil

class MascoteApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Move Mascote")
        self.running = False
        self.interval = 5
        self.remaining = 5
        self.cycle_count = 0

        # Garante que o arquivo de log exista
        if not os.path.exists("cycle_log.txt"):
            with open("cycle_log.txt", "w", encoding="utf-8") as f:
                f.write("Log de ciclos iniciado.\n")

        # Mascote animado
        self.frames = []
        try:
            gif = Image.open("mascote.gif")
            for frame in range(0, getattr(gif, "n_frames", 1)):
                gif.seek(frame)
                frame_image = ImageTk.PhotoImage(gif.copy())
                self.frames.append(frame_image)
        except Exception as e:
            print("Erro ao carregar mascote.gif:", e)
            self.frames = []

        self.img_label = tk.Label(root)
        self.img_label.pack()
        self.current_frame = 0
        if self.frames:
            self.animate_gif()

        # Interface
        self.lbl_intervalo = tk.Label(root, text="Intervalo (segundos):")
        self.lbl_intervalo.pack()
        self.edt_intervalo = tk.Entry(root)
        self.edt_intervalo.insert(0, "300")
        self.edt_intervalo.pack()
        self.lbl_contagem = tk.Label(root, text="Proximo movimento em: 0")
        self.lbl_contagem.pack()
        self.lbl_ciclos = tk.Label(root, text="Ciclos executados: 0")
        self.lbl_ciclos.pack()
        self.chk_som_var = tk.BooleanVar()
        self.chk_som = tk.Checkbutton(root, text="Som", variable=self.chk_som_var, command=self.on_toggle_sound)
        self.chk_som.pack()
        self.chk_telemetria_var = tk.BooleanVar(value=True)
        self.chk_telemetria = tk.Checkbutton(root, text="Telemetria", variable=self.chk_telemetria_var, command=self.on_toggle_telemetria)
        self.chk_telemetria.pack()
        self.chk_sistema_var = tk.BooleanVar(value=False)
        self.chk_sistema = tk.Checkbutton(root, text="Telemetria do Sistema", variable=self.chk_sistema_var, command=self.on_toggle_sistema)
        self.chk_sistema.pack()
        self.btn_desativar = tk.Button(root, text="Ativar", command=self.toggle)
        self.btn_desativar.pack()

        # Área de log em tempo real (footer) - split horizontal
        self.log_frame = tk.Frame(root)
        self.log_frame.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Log da aplicação
        self.app_log_label = tk.Label(self.log_frame, text="Log da Aplicação:")
        self.app_log_label.pack(side=tk.TOP, anchor=tk.W)
        self.app_log_text = tk.Text(self.log_frame, height=8, wrap=tk.WORD, state=tk.DISABLED)
        self.app_scrollbar = tk.Scrollbar(self.log_frame, command=self.app_log_text.yview)
        self.app_log_text.config(yscrollcommand=self.app_scrollbar.set)
        self.app_log_text.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.app_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Log do sistema
        self.system_log_label = tk.Label(self.log_frame, text="Log do Sistema:")
        self.system_log_label.pack(side=tk.TOP, anchor=tk.W)
        self.system_log_text = tk.Text(self.log_frame, height=8, wrap=tk.WORD, state=tk.DISABLED)
        self.system_scrollbar = tk.Scrollbar(self.log_frame, command=self.system_log_text.yview)
        self.system_log_text.config(yscrollcommand=self.system_scrollbar.set)
        self.system_log_text.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.system_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.timer_thread = None

        # Loga inicialização
        self.log_event("Aplicação iniciada.")

    def log_event(self, mensagem):
        if self.chk_telemetria_var.get():
            log_line = f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} - EVENTO: {mensagem}"
            with open("cycle_log.txt", "a", encoding="utf-8") as f:
                f.write(log_line + "\n")
            self.root.after(0, lambda: self.append_app_log(log_line))

    def append_app_log(self, message):
        self.app_log_text.config(state=tk.NORMAL)
        self.app_log_text.insert(tk.END, message + '\n')
        self.app_log_text.config(state=tk.DISABLED)
        self.app_log_text.see(tk.END)

    def append_system_log(self, message):
        self.system_log_text.config(state=tk.NORMAL)
        self.system_log_text.insert(tk.END, message + '\n')
        self.system_log_text.config(state=tk.DISABLED)
        self.system_log_text.see(tk.END)

    def log_system_telemetry(self):
        if self.chk_sistema_var.get():
            try:
                cpu = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory().percent
                disk = psutil.disk_usage('/').percent
                log_line = f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} - SISTEMA: CPU {cpu}%, Memória {memory}%, Disco {disk}%"
                with open("cycle_log.txt", "a", encoding="utf-8") as f:
                    f.write(log_line + "\n")
                self.root.after(0, lambda: self.append_system_log(log_line))
            except Exception as e:
                if self.chk_telemetria_var.get():
                    self.log_event(f"Erro ao obter telemetria do sistema: {e}")

    def animate_gif(self):
        if self.frames:
            self.img_label.config(image=self.frames[self.current_frame])
            self.current_frame = (self.current_frame + 1) % len(self.frames)
            self.root.after(100, self.animate_gif)

    def toggle(self):
        if self.running:
            self.running = False
            self.btn_desativar.config(text="Ativar")
            self.log_event("Ciclo desativado pelo usuário.")
        else:
            try:
                self.interval = int(self.edt_intervalo.get())
            except ValueError:
                self.interval = 5
            if self.interval < 1:
                self.interval = 5
            self.remaining = self.interval
            self.cycle_count = 0
            self.lbl_ciclos.config(text="Ciclos executados: 0")
            self.running = True
            self.btn_desativar.config(text="Desativar")
            self.log_event(f"Ciclo ativado pelo usuário. Intervalo: {self.interval} segundos.")
            self.start_timer()

    def on_toggle_sound(self):
        if self.chk_som_var.get():
            self.log_event("Som ativado pelo usuário.")
        else:
            self.log_event("Som desativado pelo usuário.")

    def on_toggle_telemetria(self):
        status = "ativada" if self.chk_telemetria_var.get() else "desativada"
        log_line = f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} - EVENTO: Telemetria {status} pelo usuário."
        with open("cycle_log.txt", "a", encoding="utf-8") as f:
            f.write(log_line + "\n")
        self.root.after(0, lambda: self.append_app_log(log_line))

    def on_toggle_sistema(self):
        status = "ativada" if self.chk_sistema_var.get() else "desativada"
        log_line = f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} - EVENTO: Telemetria do Sistema {status} pelo usuário."
        with open("cycle_log.txt", "a", encoding="utf-8") as f:
            f.write(log_line + "\n")
        self.root.after(0, lambda: self.append_system_log(log_line))

    def start_timer(self):
        def run():
            while self.running:
                self.lbl_contagem.config(text=f"Proximo movimento em: {self.remaining}")
                if self.remaining <= 0:
                    # Executa sequência de atividades para manter sistema ativo
                    # Cada função tem seu próprio tratamento de erro
                    success_count = 0
                    
                    # Movimento do mouse (essencial)
                    try:
                        # Ocasionalmente faz múltiplos movimentos (10% das vezes)
                        if random.random() < 0.1:
                            self.log_event("Executando sequência de múltiplos movimentos...")
                            movements = random.randint(2, 4)
                            for i in range(movements):
                                self.move_mouse()
                                time.sleep(random.uniform(0.2, 0.8))
                            self.log_event(f"Sequência de {movements} movimentos concluída.")
                        else:
                            self.move_mouse()
                        success_count += 1
                    except Exception as e:
                        self.log_event(f"Falha no movimento do mouse: {e}")
                    
                    # Pressionar tecla (essencial)
                    try:
                        self.press_key()
                        success_count += 1
                    except Exception as e:
                        self.log_event(f"Falha ao pressionar tecla: {e}")
                    
                    # Clique no Teams (opcional - não deve afetar simulação)
                    try:
                        self.click_on_teams_icon()
                    except Exception as e:
                        self.log_event(f"Clique no Teams falhou (normal se não estiver aberto): {e}")
                    
                    # Manter Teams ativo (opcional - não deve afetar simulação)
                    try:
                        self.keep_teams_active()
                    except Exception as e:
                        self.log_event(f"Ativação do Teams falhou (normal se não estiver aberto): {e}")
                    
                    # Som opcional
                    if self.chk_som_var.get():
                        try:
                            self.root.bell()
                        except:
                            pass  # Som é opcional
                    
                    self.cycle_count += 1
                    self.lbl_ciclos.config(text=f"Ciclos executados: {self.cycle_count}")
                    self.log_cycle_count()
                    
                    # Log do resultado do ciclo
                    if success_count >= 2:
                        self.log_event(f"Ciclo automático #{self.cycle_count} executado com sucesso ({success_count}/2 operações essenciais).")
                    else:
                        self.log_event(f"Ciclo automático #{self.cycle_count} executado com falhas ({success_count}/2 operações essenciais).")
                    
                    self.log_system_telemetry()
                    
                    self.remaining = self.interval
                else:
                    self.remaining -= 1
                time.sleep(1)
        self.timer_thread = threading.Thread(target=run, daemon=True)
        self.timer_thread.start()

    def move_mouse(self):
        try:
            # Obtém posição atual e dimensões da tela
            current_x, current_y = pyautogui.position()
            screen_width, screen_height = pyautogui.size()
            
            # Escolhe aleatoriamente o tipo de movimento
            movement_type = random.choice([
                "micro_movement",     # Movimento muito pequeno
                "small_movement",     # Movimento pequeno
                "medium_movement",    # Movimento médio
                "circular_movement",  # Movimento circular
                "random_corner"       # Movimento para área aleatória da tela
            ])
            
            if movement_type == "micro_movement":
                # Movimento microscópico (1-5 pixels)
                move_x = random.randint(-5, 5)
                move_y = random.randint(-5, 5)
                new_x = max(10, min(screen_width - 10, current_x + move_x))
                new_y = max(10, min(screen_height - 10, current_y + move_y))
                duration = random.uniform(0.1, 0.3)
                
            elif movement_type == "small_movement":
                # Movimento pequeno (10-30 pixels)
                move_x = random.randint(-30, 30)
                move_y = random.randint(-30, 30)
                new_x = max(10, min(screen_width - 10, current_x + move_x))
                new_y = max(10, min(screen_height - 10, current_y + move_y))
                duration = random.uniform(0.3, 0.7)
                
            elif movement_type == "medium_movement":
                # Movimento médio (50-100 pixels)
                move_x = random.randint(-100, 100)
                move_y = random.randint(-100, 100)
                new_x = max(50, min(screen_width - 50, current_x + move_x))
                new_y = max(50, min(screen_height - 50, current_y + move_y))
                duration = random.uniform(0.5, 1.0)
                
            elif movement_type == "circular_movement":
                # Movimento em pequeno círculo
                angle = random.uniform(0, 2 * 3.14159)  # Ângulo aleatório
                radius = random.randint(15, 40)  # Raio do círculo
                move_x = int(radius * random.uniform(0.5, 1.0) * (1 if random.random() > 0.5 else -1))
                move_y = int(radius * random.uniform(0.5, 1.0) * (1 if random.random() > 0.5 else -1))
                new_x = max(50, min(screen_width - 50, current_x + move_x))
                new_y = max(50, min(screen_height - 50, current_y + move_y))
                duration = random.uniform(0.8, 1.2)
                
            else:  # random_corner
                # Movimento para área aleatória da tela (mais natural)
                margin = 100
                new_x = random.randint(margin, screen_width - margin)
                new_y = random.randint(margin, screen_height - margin)
                duration = random.uniform(1.0, 2.0)
            
            # Adiciona pequena variação na duração
            duration *= random.uniform(0.8, 1.2)
            
            # Move o mouse com траектória mais natural
            if movement_type == "circular_movement":
                # Para movimento circular, faz curva suave
                mid_x = (current_x + new_x) // 2 + random.randint(-20, 20)
                mid_y = (current_y + new_y) // 2 + random.randint(-20, 20)
                pyautogui.moveTo(mid_x, mid_y, duration=duration/2)
                pyautogui.moveTo(new_x, new_y, duration=duration/2)
            else:
                # Movimento direto com velocidade variável
                pyautogui.moveTo(new_x, new_y, duration=duration)
            
            # Log com tipo de movimento
            distance = ((new_x - current_x)**2 + (new_y - current_y)**2)**0.5
            self.log_event(f"Mouse movido ({movement_type}): ({current_x},{current_y}) → ({new_x},{new_y}) | Distância: {distance:.1f}px | Duração: {duration:.2f}s")
            
        except Exception as e:
            self.log_event(f"Erro ao mover mouse: {e}")

    def press_key(self):
        # Pressiona barra de espaço para simular atividade
        try:
            pyautogui.press('space')
            self.log_event("Tecla espaço pressionada.")
        except Exception as e:
            self.log_event(f"Erro ao pressionar tecla: {e}")

    def click_on_teams_icon(self):
        # Ajuste a posição conforme necessário para o seu Teams
        try:
            # Verifica se a posição está dentro da tela
            screen_width, screen_height = pyautogui.size()
            if 50 < screen_width and 1050 < screen_height:
                # Salva posição atual do mouse
                original_x, original_y = pyautogui.position()
                
                # Tenta clicar no Teams
                pyautogui.moveTo(50, 1050, duration=0.3)
                pyautogui.click()
                
                # Retorna mouse para posição original
                pyautogui.moveTo(original_x, original_y, duration=0.2)
                
                self.log_event("Tentativa de clique no ícone do Teams executada.")
            else:
                self.log_event("Posição do Teams fora da tela. Clique ignorado, continuando simulação.")
        except Exception as e:
            # Falha no clique do Teams não deve afetar a simulação
            self.log_event(f"Teams não acessível (isso é normal se não estiver aberto): {e}")
            self.log_event("Simulação continua normalmente sem o Teams.")

    def keep_teams_active(self):
        # Múltiplas estratégias para manter o Teams ativo
        try:
            # Pressiona Shift (tecla silenciosa que mantém atividade)
            pyautogui.press('shift')
            self.log_event("Tecla Shift pressionada para manter atividade do sistema.")
            
            # Simula pequeno movimento do mouse (adicional)
            current_x, current_y = pyautogui.position()
            pyautogui.moveTo(current_x + 1, current_y)
            pyautogui.moveTo(current_x, current_y)
            
        except Exception as e:
            # Falha na ativação do Teams não deve parar a simulação
            self.log_event(f"Erro ao manter Teams ativo (continuando simulação): {e}")
            # Tenta uma estratégia alternativa simples
            try:
                pyautogui.press('ctrl')
                self.log_event("Estratégia alternativa: Ctrl pressionado para manter atividade.")
            except:
                self.log_event("Todas as estratégias de ativação falharam, mas simulação continua.")

    def log_cycle_count(self):
        if self.chk_telemetria_var.get():
            log_line = f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} - Total de ciclos: {self.cycle_count}"
            with open("cycle_log.txt", "a", encoding="utf-8") as f:
                f.write(log_line + "\n")
            self.root.after(0, lambda: self.append_app_log(log_line))

if __name__ == "__main__":
    # Constantes de layout para facilitar futuros ajustes
    WINDOW_WIDTH = 400
    WINDOW_HEIGHT = 800

    root = tk.Tk()
    root.iconbitmap("mascote.ico")
    root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")  # Tamanho fixo da janela
    root.resizable(False, False)  # Impede redimensionamento
    app = MascoteApp(root)
    root.mainloop()
