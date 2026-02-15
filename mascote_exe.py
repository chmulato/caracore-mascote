#!/usr/bin/env python3
"""
Script para compilar o MascoteApp em executáveis Windows (.exe)

Este script automatiza o processo de criação de executáveis usando PyInstaller.
- mascote.exe: aplicativo principal (manter ativo no Teams).
- mascote_blackbox.exe: bloqueio de telemetria na rede (requer admin).

Uso:
  python mascote_exe.py          # só mascote.exe
  python mascote_exe.py --all    # mascote.exe + mascote_blackbox.exe
  python mascote_exe.py --blackbox   # só mascote_blackbox.exe

Autor: Christian Vladimir Uhdre Mulato
Data: Campo Largo, 02 de Outubro de 2025.
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

class MascoteCompiler:
    def __init__(self):
        self.script_dir = Path(__file__).parent.absolute()
        self.source_file = self.script_dir / "mascote.py"
        self.source_blackbox = self.script_dir / "mascote_blackbox.py"
        self.spec_blackbox = self.script_dir / "mascote_blackbox.spec"
        self.dist_dir = self.script_dir / "dist"
        self.build_dir = self.script_dir / "build"
        self.spec_file = self.script_dir / "mascote.spec"
        
        # Arquivos de recursos necessários (mascote principal)
        self.resource_files = [
            "mascote.gif",
            "mascote.ico",
            "boneco.ico"
        ]
        self.resource_blackbox = ["mascote.ico"]
        
    def check_requirements(self):
        """Verifica se todos os requisitos estão instalados"""
        print("Verificando requisitos...")
        
        # Verifica se o arquivo principal existe
        if not self.source_file.exists():
            print(f"ERRO: {self.source_file} nao encontrado.")
            return False
            
        # Verifica arquivos de recursos
        missing_resources = []
        for resource in self.resource_files:
            resource_path = self.script_dir / resource
            if not resource_path.exists():
                missing_resources.append(resource)
                
        if missing_resources:
            print(f"AVISO: Recursos nao encontrados: {', '.join(missing_resources)}")
            print("   O executavel sera criado, mas pode nao funcionar corretamente.")
            
        return True
        
    def install_pyinstaller(self):
        """Instala o PyInstaller se não estiver disponível"""
        print("Verificando PyInstaller...")
        
        try:
            import PyInstaller
            print("PyInstaller instalado.")
            return True
        except ImportError:
            print("Instalando PyInstaller...")
            try:
                subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], 
                             check=True, capture_output=True, text=True)
                print("PyInstaller instalado com sucesso.")
                return True
            except subprocess.CalledProcessError as e:
                print(f"ERRO ao instalar PyInstaller: {e}")
                return False
                
    def clean_previous_builds(self):
        """Remove builds anteriores"""
        print("Limpando builds anteriores...")
        
        # Remove diretórios de build
        for directory in [self.dist_dir, self.build_dir]:
            if directory.exists():
                shutil.rmtree(directory)
                print(f"   Removido: {directory}")
                
        # Remove arquivo .spec se existir
        if self.spec_file.exists():
            self.spec_file.unlink()
            print(f"   Removido: {self.spec_file}")
            
    def create_executable(self):
        """Cria o executável usando PyInstaller"""
        print("Compilando executavel...")
        
        # Monta comando do PyInstaller
        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--onefile",                    # Arquivo único
            "--windowed",                   # Sem console
            "--name", "mascote",            # Nome do executável
            "--icon", "mascote.ico",        # Ícone do executável
            "--distpath", str(self.dist_dir),  # Diretório de saída
            "--workpath", str(self.build_dir), # Diretório de trabalho
            "--clean",                      # Limpa cache
            "--noconfirm",                  # Não pede confirmação
            "--hidden-import", "pyautogui",  # Incluir no exe (evita ModuleNotFoundError)
            "--hidden-import", "PIL",
            "--hidden-import", "PIL.Image",
            "--hidden-import", "PIL.ImageTk",
        ]
        
        # Adiciona arquivos de dados (recursos)
        for resource in self.resource_files:
            resource_path = self.script_dir / resource
            if resource_path.exists():
                cmd.extend(["--add-data", f"{resource_path};."])
                
        # Adiciona arquivo principal
        cmd.append(str(self.source_file))
        
        try:
            print(f"   Executando: {' '.join(cmd)}")
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            print("Compilacao concluida com sucesso.")
            return True
            
        except subprocess.CalledProcessError as e:
            print("ERRO durante a compilacao:")
            print(f"   Código de saída: {e.returncode}")
            print(f"   Stdout: {e.stdout}")
            print(f"   Stderr: {e.stderr}")
            return False
            
    def copy_resources_to_dist(self):
        """Copia recursos necessários para o diretório dist"""
        print("Copiando recursos adicionais...")
        
        if not self.dist_dir.exists():
            print("ERRO: Diretorio dist nao encontrado.")
            return False
            
        # Copia arquivos de recursos para junto do executável
        for resource in self.resource_files:
            resource_path = self.script_dir / resource
            if resource_path.exists():
                dest_path = self.dist_dir / resource
                shutil.copy2(resource_path, dest_path)
                print(f"   Copiado: {resource} -> dist/")
                
        return True
        
    def check_requirements_blackbox(self):
        """Verifica requisitos para compilar o Mascote BlackBox."""
        print("Verificando requisitos BlackBox...")
        if not self.source_blackbox.exists():
            print(f"ERRO: {self.source_blackbox} nao encontrado.")
            return False
        if not self.spec_blackbox.exists():
            print(f"ERRO: {self.spec_blackbox} nao encontrado.")
            return False
        for r in self.resource_blackbox:
            if not (self.script_dir / r).exists():
                print(f"AVISO: Recurso nao encontrado: {r}")
        return True

    def build_blackbox(self):
        """Compila mascote_blackbox.exe usando o .spec (UAC admin)."""
        print("Compilando Mascote BlackBox...")
        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--noconfirm",
            str(self.spec_blackbox),
        ]
        try:
            result = subprocess.run(cmd, cwd=str(self.script_dir), check=True, capture_output=True, text=True)
            print("Mascote BlackBox compilado com sucesso.")
            return True
        except subprocess.CalledProcessError as e:
            print(f"ERRO ao compilar BlackBox: {e.stderr or e}")
            return False

    def verify_executable(self, name="mascote"):
        """Verifica se o executável foi criado corretamente."""
        print("Verificando executavel...")
        exe_path = self.dist_dir / f"{name}.exe"
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"Executavel criado: {exe_path} ({size_mb:.2f} MB)")
            return True
        print(f"ERRO: Executavel nao encontrado: {exe_path}")
        return False

    def list_dist(self):
        """Lista conteúdo do diretório dist."""
        if not self.dist_dir.exists():
            return
        print("Conteudo do diretorio dist:")
        for item in sorted(self.dist_dir.iterdir()):
            if item.is_file():
                size_kb = item.stat().st_size / 1024
                print(f"   {item.name} ({size_kb:.1f} KB)")
            
    def run_compilation(self, blackbox_only=False, build_all=False):
        """Executa o processo de compilação.
        blackbox_only: compila só mascote_blackbox.exe (não limpa dist).
        build_all: compila mascote.exe e mascote_blackbox.exe.
        """
        if build_all:
            return self._run_compilation_all()
        if blackbox_only:
            return self._run_compilation_blackbox_only()
        return self._run_compilation_mascote_only()

    def _run_compilation_mascote_only(self):
        """Compila apenas mascote.exe."""
        print("Iniciando compilacao do MascoteApp para Windows")
        print("=" * 60)
        if not self.check_requirements():
            return False
        if not self.install_pyinstaller():
            return False
        self.clean_previous_builds()
        if not self.create_executable():
            return False
        if not self.copy_resources_to_dist():
            return False
        if not self.verify_executable("mascote"):
            return False
        self.list_dist()
        print("=" * 60)
        print("Compilacao concluida com sucesso.")
        print(f"Executavel: {self.dist_dir / 'mascote.exe'}")
        return True

    def _run_compilation_blackbox_only(self):
        """Compila apenas mascote_blackbox.exe (mantém dist/ existente)."""
        print("Compilando Mascote BlackBox (bloqueio de telemetria)")
        print("=" * 60)
        if not self.check_requirements_blackbox():
            return False
        if not self.install_pyinstaller():
            return False
        if not self.build_blackbox():
            return False
        if not self.verify_executable("mascote_blackbox"):
            return False
        self.list_dist()
        print("=" * 60)
        print("Mascote BlackBox compilado com sucesso.")
        print(f"Executavel: {self.dist_dir / 'mascote_blackbox.exe'}")
        print("Execute como Administrador para aplicar o bloqueio.")
        return True

    def _run_compilation_all(self):
        """Compila mascote.exe e mascote_blackbox.exe."""
        print("Compilando MascoteApp e Mascote BlackBox")
        print("=" * 60)
        if not self.check_requirements():
            return False
        if not self.check_requirements_blackbox():
            return False
        if not self.install_pyinstaller():
            return False
        self.clean_previous_builds()
        if not self.create_executable():
            return False
        if not self.copy_resources_to_dist():
            return False
        if not self.verify_executable("mascote"):
            return False
        if not self.build_blackbox():
            return False
        if not self.verify_executable("mascote_blackbox"):
            return False
        self.list_dist()
        print("=" * 60)
        print("Compilacao concluida com sucesso.")
        print(f"{self.dist_dir / 'mascote.exe'} (MascoteApp)")
        print(f"{self.dist_dir / 'mascote_blackbox.exe'} (Bloqueio telemetria; executar como admin)")
        return True

def main():
    """Função principal. Argumentos: --all (mascote + blackbox), --blackbox (só blackbox)."""
    blackbox_only = "--blackbox" in sys.argv
    build_all = "--all" in sys.argv
    try:
        compiler = MascoteCompiler()
        success = compiler.run_compilation(blackbox_only=blackbox_only, build_all=build_all)
        if success:
            print("\nProcesso concluido com sucesso.")
            test_exe = input("\nDeseja testar um executavel agora? (s/n): ").lower().strip()
            if test_exe in ["s", "sim", "y", "yes"]:
                to_run = None
                if compiler.dist_dir.exists():
                    if blackbox_only and (compiler.dist_dir / "mascote_blackbox.exe").exists():
                        to_run = compiler.dist_dir / "mascote_blackbox.exe"
                    elif (compiler.dist_dir / "mascote.exe").exists():
                        to_run = compiler.dist_dir / "mascote.exe"
                if to_run:
                    print(f"Executando {to_run.name}...")
                    subprocess.Popen([str(to_run)], cwd=str(compiler.dist_dir))
                else:
                    print("Nenhum executavel encontrado para teste.")
        else:
            print("\nCompilacao falhou.")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\nCompilacao cancelada pelo usuario.")
        sys.exit(1)
    except Exception as e:
        print(f"\nErro inesperado: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()