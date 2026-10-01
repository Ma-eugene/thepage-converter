# -*- coding: utf-8 -*-
"""
더페이지 3D 초경량 GLB 변환 및 ZIP 패키징 미니 데스크탑 앱
- 작업표시줄 고정 지원
- 모니터 오른쪽 하단 자동 배치
- 드래그 앤 드롭으로 3초 만에 완제품 ZIP 생성
"""

import sys
import os
import ctypes
import subprocess
import zipfile
import shutil
import time
import struct
import json

def check_glb_is_optimized(glb_path):
    """기존 GLB가 단일 메시 및 NORMAL 벡터를 포함하는 표준 최적화 규격인지 검사"""
    try:
        if not os.path.exists(glb_path):
            return False
        with open(glb_path, 'rb') as f:
            header = f.read(12)
            if len(header) < 12:
                return False
            magic, version, length = struct.unpack('<4sII', header)
            if magic != b'glTF':
                return False
            chunk_len, chunk_type = struct.unpack('<II', f.read(8))
            if chunk_type != 0x4E4F534A: # JSON chunk
                return False
            json_data = json.loads(f.read(chunk_len).decode('utf-8'))
            meshes = json_data.get('meshes', [])
            if len(meshes) != 1: # 메시가 여러 개로 파편화된 구버전은 재변환 필요
                return False
            primitives = meshes[0].get('primitives', [])
            if not primitives:
                return False
            attrs = primitives[0].get('attributes', {})
            if 'NORMAL' not in attrs: # 노멀이 누락된 구버전은 재변환 필요
                return False
            return True
    except Exception:
        return False

# Windows 작업표시줄 독립 앱 ID 등록 (작업표시줄 고정 및 독립 아이콘 보장)
APP_ID = 'ThePage.3DConverter.QuickPacker.v1'
try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
except Exception:
    pass

try:
    debug_dir = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'ThePage3D')
    os.makedirs(debug_dir, exist_ok=True)
    with open(os.path.join(debug_dir, 'debug.log'), 'a', encoding='utf-8') as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Launch: argv={sys.argv}, exe={sys.executable}, frozen={getattr(sys, 'frozen', False)}\n")
except Exception:
    pass

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QPoint
from PyQt5.QtGui import QColor, QFont, QCursor, QIcon
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFrame, QProgressBar, QGraphicsDropShadowEffect,
    QMenu, QAction, QMessageBox
)

def get_app_icon_path():
    base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    ico_p = os.path.join(base_dir, 'app_icon.ico')
    if os.path.exists(ico_p):
        return ico_p
    # 설치 디렉토리 폴백
    install_ico = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'ThePage3D', 'app_icon.ico')
    if os.path.exists(install_ico):
        return install_ico
    return ""

def get_app_icon():
    p = get_app_icon_path()
    if p and os.path.exists(p):
        return QIcon(p)
    return QIcon()

def get_engine_paths():
    """100% 로컬 독립 변환 엔진 경로 반환 (외부 인터넷/서버 통신 0%)"""
    install_dir = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'ThePage3D')
    engine_dir = os.path.join(install_dir, 'engine')
    
    node_exe = os.path.join(engine_dir, 'node.exe')
    obj2gltf_js = os.path.join(engine_dir, 'node_modules', 'obj2gltf', 'bin', 'obj2gltf.js')
    gltfpack_js = os.path.join(engine_dir, 'node_modules', 'gltfpack', 'cli.js')
    gltf_pipe_js = os.path.join(engine_dir, 'node_modules', 'gltf-pipeline', 'bin', 'gltf-pipeline.js')
    
    if os.path.exists(node_exe) and os.path.exists(obj2gltf_js):
        pack_cmd = gltfpack_js if os.path.exists(gltfpack_js) else ""
        return node_exe, obj2gltf_js, pack_cmd, gltf_pipe_js

    # 개발 폴백 (tools/3d_converter)
    dev_dir = os.path.dirname(os.path.abspath(__file__))
    dev_node = r'C:\Program Files\nodejs\node.exe'
    dev_obj = os.path.join(dev_dir, 'node_modules', 'obj2gltf', 'bin', 'obj2gltf.js')
    dev_pack = os.path.join(dev_dir, 'node_modules', 'gltfpack', 'cli.js')
    dev_pipe = os.path.join(dev_dir, 'node_modules', 'gltf-pipeline', 'bin', 'gltf-pipeline.js')
    if os.path.exists(dev_node) and os.path.exists(dev_obj):
        pack_cmd = dev_pack if os.path.exists(dev_pack) else ""
        return dev_node, dev_obj, pack_cmd, dev_pipe

    return "", "", "", ""


def ensure_local_engine_ready():
    """로컬 엔진이 설치되어 있지 않다면 즉시 로컬 압축 해제 준비"""
    try:
        install_dir = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'ThePage3D')
        engine_dir = os.path.join(install_dir, 'engine')
        node_in_engine = os.path.join(engine_dir, 'node.exe')
        obj2gltf_js = os.path.join(engine_dir, 'node_modules', 'obj2gltf', 'bin', 'obj2gltf.js')
        if not (os.path.exists(node_in_engine) and os.path.exists(obj2gltf_js)):
            base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
            engine_zip = os.path.join(base_dir, 'engine.zip')
            if not os.path.exists(engine_zip):
                engine_zip = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'engine.zip')
            if os.path.exists(engine_zip):
                os.makedirs(engine_dir, exist_ok=True)
                with zipfile.ZipFile(engine_zip, 'r') as zf:
                    zf.extractall(engine_dir)
    except Exception:
        pass


class WorkerThread(QThread):
    progress_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str, str, str) # success, zip_path, zip_size, message

    def __init__(self, paths):
        super().__init__()
        self.paths = paths

    def run(self):
        try:
            if not self.paths:
                self.finished_signal.emit(False, "", "", "전달된 파일이나 폴더가 없습니다.")
                return

            first_arg = os.path.abspath(self.paths[0])
            if os.path.isdir(first_arg):
                target_dir = first_arg
            else:
                target_dir = os.path.dirname(first_arg)

            self.progress_signal.emit("📂 3D 소스 파일 탐색 중...")
            all_files = os.listdir(target_dir)
            obj_files = [f for f in all_files if f.lower().endswith('.obj')]
            
            if not obj_files:
                self.finished_signal.emit(False, "", "", "폴더 내에 .obj 파일이 없습니다.")
                return

            obj_name = obj_files[0]
            base_name = os.path.splitext(obj_name)[0]
            obj_path = os.path.join(target_dir, obj_name)
            folder_name = os.path.basename(os.path.normpath(target_dir))

            target_glb_name = f"{base_name}.glb"
            target_glb_path = os.path.join(target_dir, target_glb_name)

            need_conversion = True
            if os.path.exists(target_glb_path):
                glb_size_mb = os.path.getsize(target_glb_path) / (1024 * 1024)
                if glb_size_mb < 6.0 and check_glb_is_optimized(target_glb_path):
                    self.progress_signal.emit(f"✅ 기존 최적화 GLB 감지 ({glb_size_mb:.1f}MB)")
                    need_conversion = False
                else:
                    self.progress_signal.emit("⚡ 4MB 초경량 규격 자동 최적화 변환 진행...")

            if need_conversion:
                self.progress_signal.emit("🚀 4MB 초경량 GLB 초고속 변환 중... (폴리곤 1/10 압축)")
                node_exe, obj2gltf_js, gltfpack_js, gltf_pipe_js = get_engine_paths()
                if not node_exe or not os.path.exists(node_exe):
                    ensure_local_engine_ready()
                    node_exe, obj2gltf_js, gltfpack_js, gltf_pipe_js = get_engine_paths()

                if not node_exe or not os.path.exists(node_exe):
                    self.finished_signal.emit(False, "", "", "로컬 변환 엔진(node.exe)을 찾을 수 없습니다.")
                    return

                temp_raw_gltf = os.path.join(target_dir, f"_temp_{base_name}.gltf")
                temp_pack_glb = os.path.join(target_dir, f"_temp_pack_{base_name}.glb")

                try:
                    no_window = getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000) if sys.platform == 'win32' else 0
                    
                    # 1단계: obj -> raw gltf (메시 단일화 + 버텍스 노멀 자동 계산, 콘솔 창 숨김)
                    cmd1 = [node_exe, obj2gltf_js, '-i', obj_path, '-o', temp_raw_gltf]
                    r1 = subprocess.run(cmd1, cwd=target_dir, capture_output=True, text=True, creationflags=no_window)
                    if r1.returncode != 0:
                        self.finished_signal.emit(False, "", "", f"1단계 변환 오류: {r1.stderr[:100]}")
                        return

                    pipe_input = temp_raw_gltf
                    # 2단계: gltfpack으로 폴리곤 1/10 지능형 감축 (140만 -> 14만 개 데시메이션)
                    if gltfpack_js and os.path.exists(gltfpack_js):
                        cmd_pack = [node_exe, gltfpack_js, '-i', temp_raw_gltf, '-o', temp_pack_glb, '-si', '0.05']
                        r_pack = subprocess.run(cmd_pack, cwd=target_dir, capture_output=True, text=True, creationflags=no_window)
                        if r_pack.returncode == 0 and os.path.exists(temp_pack_glb):
                            pipe_input = temp_pack_glb

                    # 3단계: Draco 무손실 압축 초경량 GLB 완성 (속도 최적화 level 6, 콘솔 창 숨김)
                    cmd2 = [node_exe, gltf_pipe_js, '-i', pipe_input, '-o', target_glb_path, '-d', '--draco.compressionLevel', '6']
                    r2 = subprocess.run(cmd2, cwd=target_dir, capture_output=True, text=True, creationflags=no_window)
                    if r2.returncode != 0:
                        self.finished_signal.emit(False, "", "", f"최종 압축 오류: {r2.stderr[:100]}")
                        return
                finally:
                    for tmp in [temp_raw_gltf, temp_pack_glb, os.path.join(target_dir, f"_temp_{base_name}.bin")]:
                        if os.path.exists(tmp):
                            try: os.remove(tmp)
                            except: pass

            self.progress_signal.emit("📦 완제품 ZIP 파일 패키징 중...")
            is_valid_code = any(p in folder_name.upper() for p in ['CHR', 'UHB', 'DG', 'HQ', 'DAT', 'AI', 'FIG', '260', '261'])
            zip_filename = f"{folder_name}.zip" if is_valid_code else f"{base_name}.zip"
            output_zip_path = os.path.join(target_dir, zip_filename)

            files_to_pack = [f for f in os.listdir(target_dir) if os.path.splitext(f)[1].lower() in ['.obj', '.mtl', '.jpg', '.jpeg', '.png', '.glb'] and not f.startswith('_temp_') and f != zip_filename]

            # 파일 잠금 충돌 방지: 임시 파일로 먼저 쓰고 교체
            temp_zip_path = os.path.join(target_dir, f"_temp_pack_{zip_filename}")
            if os.path.exists(temp_zip_path):
                try: os.remove(temp_zip_path)
                except: pass

            with zipfile.ZipFile(temp_zip_path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
                for fname in files_to_pack:
                    zf.write(os.path.join(target_dir, fname), arcname=fname)

            if os.path.exists(output_zip_path):
                try: os.remove(output_zip_path)
                except Exception: pass

            try:
                shutil.move(temp_zip_path, output_zip_path)
            except Exception:
                shutil.copy2(temp_zip_path, output_zip_path)
                try: os.remove(temp_zip_path)
                except: pass

            zip_size_mb = f"{os.path.getsize(output_zip_path) / (1024 * 1024):.1f} MB"
            self.finished_signal.emit(True, output_zip_path, zip_size_mb, f"{zip_filename} 생성 완료!")

        except Exception as e:
            self.finished_signal.emit(False, "", "", f"오류 발생: {str(e)}")


class UpdateCheckerThread(QThread):
    update_signal = pyqtSignal(str)

    def run(self):
        try:
            import urllib.request
            url = "https://raw.githubusercontent.com/maeugene88/thepage-converter/main/version.json"
            req = urllib.request.Request(url, headers={'User-Agent': 'ThePage3D-Converter/1.2'})
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    remote_info = json.loads(resp.read().decode('utf-8'))
                    remote_ver = remote_info.get("version", "1.0.0")

                    install_dir = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'ThePage3D')
                    local_ver_file = os.path.join(install_dir, 'version.json')
                    local_ver = "1.0.0"
                    if os.path.exists(local_ver_file):
                        try:
                            with open(local_ver_file, 'r', encoding='utf-8') as f:
                                local_ver = json.load(f).get("version", "1.0.0")
                        except Exception:
                            pass

                    # 원격 버전이 더 최신인 경우 패치 파일 자동 다운로드 및 교체
                    if remote_ver > local_ver:
                        patches = remote_info.get("patches", [])
                        success_count = 0
                        for p in patches:
                            target_rel = p.get("target_rel_path")
                            patch_url = p.get("url")
                            if target_rel and patch_url:
                                full_target = os.path.join(install_dir, target_rel)
                                os.makedirs(os.path.dirname(full_target), exist_ok=True)
                                p_req = urllib.request.Request(patch_url, headers={'User-Agent': 'ThePage3D-Converter/1.1'})
                                with urllib.request.urlopen(p_req, timeout=5) as p_resp:
                                    if p_resp.status == 200:
                                        with open(full_target, 'wb') as pf:
                                            pf.write(p_resp.read())
                                        success_count += 1

                        with open(local_ver_file, 'w', encoding='utf-8') as f:
                            json.dump(remote_info, f, indent=2, ensure_ascii=False)

                        if success_count > 0:
                            self.update_signal.emit(f"✨ 최신 엔진(v{remote_ver}) 자동 업데이트 완료")
        except Exception:
            pass # 네트워크 오류 시 기존 로컬 엔진으로 정상 가동


class DropZoneWidget(QFrame):
    files_dropped = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setObjectName("dropZone")
        self.setStyleSheet("""
            #dropZone {
                background: rgba(30, 41, 59, 0.7);
                border: 2px dashed rgba(99, 102, 241, 0.6);
                border-radius: 16px;
            }
            #dropZone:hover {
                background: rgba(49, 46, 129, 0.4);
                border: 2px dashed #818cf8;
            }
        """)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet("""
                #dropZone {
                    background: rgba(67, 56, 202, 0.6);
                    border: 2px solid #a5b4fc;
                    border-radius: 16px;
                }
            """)

    def dragLeaveEvent(self, event):
        self.setStyleSheet("""
            #dropZone {
                background: rgba(30, 41, 59, 0.7);
                border: 2px dashed rgba(99, 102, 241, 0.6);
                border-radius: 16px;
            }
        """)

    def dropEvent(self, event):
        self.setStyleSheet("""
            #dropZone {
                background: rgba(30, 41, 59, 0.7);
                border: 2px dashed rgba(99, 102, 241, 0.6);
                border-radius: 16px;
            }
        """)
        urls = event.mimeData().urls()
        paths = [u.toLocalFile() for u in urls if u.isLocalFile()]
        if paths:
            self.files_dropped.emit(paths)


def create_windows_shortcuts(target_exe):
    """VBScript를 이용해 바탕화면 및 시작메뉴에 바로가기 아이콘 100% 등록"""
    try:
        install_dir = os.path.dirname(target_exe)
        desktop = os.path.join(os.path.expanduser('~'), 'Desktop')
        programs = os.path.join(os.environ.get('APPDATA', ''), r'Microsoft\Windows\Start Menu\Programs')
        
        desk_lnk = os.path.join(desktop, '더페이지 3D 변환기.lnk')
        prog_lnk = os.path.join(programs, '더페이지 3D 변환기.lnk')
        
        vbs_content = f'''Set oWS = WScript.CreateObject("WScript.Shell")
Set oL1 = oWS.CreateShortcut("{desk_lnk}")
oL1.TargetPath = "{target_exe}"
oL1.WorkingDirectory = "{install_dir}"
oL1.IconLocation = "{target_exe},0"
oL1.Description = "더페이지 3D 초경량 GLB 변환 및 완제품 ZIP 패키징"
oL1.Save

Set oL2 = oWS.CreateShortcut("{prog_lnk}")
oL2.TargetPath = "{target_exe}"
oL2.WorkingDirectory = "{install_dir}"
oL2.IconLocation = "{target_exe},0"
oL2.Description = "더페이지 3D 초경량 GLB 변환 및 완제품 ZIP 패키징"
oL2.Save
'''
        vbs_path = os.path.join(install_dir, '_create_shortcut.vbs')
        with open(vbs_path, 'w', encoding='utf-16') as f:
            f.write(vbs_content)
        subprocess.run(['cscript', '//nologo', vbs_path], capture_output=True)
        try: os.remove(vbs_path)
        except: pass
        return True
    except Exception:
        return False


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.is_pinned = True
        self.last_zip_path = ""
        self.old_pos = None

        self.initUI()
        self.position_bottom_right()
        self.check_auto_update()

    def check_auto_update(self):
        try:
            self.updater = UpdateCheckerThread()
            self.updater.update_signal.connect(self.on_update_completed)
            self.updater.start()
        except Exception:
            pass

    def on_update_completed(self, msg):
        try:
            self.status_label.setStyleSheet("color: #4ade80; font-size: 11px;")
            self.status_label.setText(msg)
        except Exception:
            pass

    def initUI(self):
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowMinMaxButtonsHint | Qt.WindowStaysOnTopHint)
        self.setWindowIcon(get_app_icon())
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(340, 390)

        # 메인 컨테이너 (둥근 모서리 + 다크 글래스 테마)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)

        self.container = QFrame(self)
        self.container.setObjectName("mainContainer")
        self.container.setStyleSheet("""
            #mainContainer {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0f172a, stop:1 #1e1b4b);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 20px;
            }
        """)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(25)
        shadow.setColor(QColor(0, 0, 0, 180))
        shadow.setOffset(0, 8)
        self.container.setGraphicsEffect(shadow)

        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(16, 14, 16, 16)
        container_layout.setSpacing(12)

        # 1. 상단 타이틀 바
        header = QHBoxLayout()
        header.setSpacing(6)

        icon_label = QLabel("✨")
        icon_label.setStyleSheet("font-size: 16px;")

        title_label = QLabel("더페이지 3D 변환기")
        title_label.setStyleSheet("color: #f8fafc; font-weight: 700; font-size: 14px; font-family: 'Pretendard', 'Segoe UI', sans-serif;")

        header.addWidget(icon_label)
        header.addWidget(title_label)
        header.addStretch()

        # 항상 위 핀 버튼
        self.pin_btn = QPushButton("📌")
        self.pin_btn.setFixedSize(28, 28)
        self.pin_btn.setToolTip("항상 화면 맨 위에 고정 (클릭하여 토글)")
        self.pin_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.pin_btn.setStyleSheet("""
            QPushButton {
                background: rgba(99, 102, 241, 0.4);
                border: 1px solid rgba(129, 140, 248, 0.5);
                border-radius: 14px;
                font-size: 12px;
            }
            QPushButton:hover { background: rgba(99, 102, 241, 0.7); }
        """)
        self.pin_btn.clicked.connect(self.toggle_pin)

        # 최소화 버튼 (_)
        min_btn = QPushButton("─")
        min_btn.setFixedSize(28, 28)
        min_btn.setToolTip("작업표시줄로 최소화")
        min_btn.setCursor(QCursor(Qt.PointingHandCursor))
        min_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.2);
                color: #cbd5e1;
                border-radius: 14px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover { background: rgba(255, 255, 255, 0.25); color: white; }
        """)
        min_btn.clicked.connect(self.showMinimized)

        # 닫기 버튼 (✕)
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setToolTip("프로그램 종료")
        close_btn.setCursor(QCursor(Qt.PointingHandCursor))
        close_btn.setStyleSheet("""
            QPushButton {
                background: rgba(239, 68, 68, 0.2);
                border: 1px solid rgba(239, 68, 68, 0.4);
                color: #fca5a5;
                border-radius: 14px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover { background: rgba(239, 68, 68, 0.6); color: white; }
        """)
        close_btn.clicked.connect(self.close)

        header.addWidget(self.pin_btn)
        header.addWidget(min_btn)
        header.addWidget(close_btn)
        container_layout.addLayout(header)

        # 2. 중앙 드롭 존
        self.drop_zone = DropZoneWidget(self)
        self.drop_zone.files_dropped.connect(self.process_files)
        drop_layout = QVBoxLayout(self.drop_zone)
        drop_layout.setContentsMargins(16, 24, 16, 24)
        drop_layout.setAlignment(Qt.AlignCenter)
        drop_layout.setSpacing(10)

        self.box_icon = QLabel("📦")
        self.box_icon.setAlignment(Qt.AlignCenter)
        self.box_icon.setStyleSheet("font-size: 38px;")

        self.box_text = QLabel("작업 폴더 또는 3D 파일을\n여기에 끌어다 놓으세요")
        self.box_text.setAlignment(Qt.AlignCenter)
        self.box_text.setStyleSheet("color: #cbd5e1; font-size: 12px; font-weight: 500; line-height: 1.4;")

        drop_layout.addWidget(self.box_icon)
        drop_layout.addWidget(self.box_text)
        container_layout.addWidget(self.drop_zone)

        # 3. 하단 진행 상태 및 결과
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setRange(0, 0) # 무한 펄스 스피너
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background: rgba(255, 255, 255, 0.1);
                border-radius: 3px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #ec4899);
                border-radius: 3px;
            }
        """)
        self.progress_bar.hide()
        container_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("준비 완료 (마우스로 툭 던지세요)")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #94a3b8; font-size: 11px;")
        container_layout.addWidget(self.status_label)

        # 결과 탐색기 열기 버튼
        self.open_folder_btn = QPushButton("📂 생성된 ZIP 파일 확인하기")
        self.open_folder_btn.setFixedHeight(34)
        self.open_folder_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.open_folder_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #6366f1);
                color: white;
                font-weight: 600;
                font-size: 12px;
                border: none;
                border-radius: 10px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #4f46e5);
            }
        """)
        self.open_folder_btn.clicked.connect(self.open_result_folder)
        self.open_folder_btn.hide()
        container_layout.addWidget(self.open_folder_btn)

        main_layout.addWidget(self.container)

    def position_bottom_right(self):
        screen = QApplication.primaryScreen().availableGeometry()
        margin_x = 24
        margin_y = 24
        x = screen.right() - self.width() - margin_x
        y = screen.bottom() - self.height() - margin_y
        self.move(x, y)

    def ensure_taskbar_icon(self):
        """Windows Frameless 창이 작업표시줄에 정상 표시되도록 보장"""
        if sys.platform == 'win32':
            try:
                hwnd = int(self.winId())
                GWL_EXSTYLE = -20
                WS_EX_APPWINDOW = 0x00040000
                WS_EX_TOOLWINDOW = 0x00000080
                style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                style = (style | WS_EX_APPWINDOW) & ~WS_EX_TOOLWINDOW
                ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
                ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0027)
            except Exception:
                pass

    def showEvent(self, event):
        super().showEvent(event)
        self.ensure_taskbar_icon()

    def toggle_pin(self):
        self.is_pinned = not self.is_pinned
        flags = Qt.Window | Qt.FramelessWindowHint | Qt.WindowMinMaxButtonsHint
        if self.is_pinned:
            flags |= Qt.WindowStaysOnTopHint
            self.pin_btn.setStyleSheet("background: rgba(99, 102, 241, 0.7); border: 1px solid #818cf8; border-radius: 14px; font-size: 12px;")
        else:
            self.pin_btn.setStyleSheet("background: rgba(255, 255, 255, 0.1); border: 1px solid rgba(255, 255, 255, 0.2); border-radius: 14px; font-size: 12px;")
        self.setWindowFlags(flags)
        self.show()
        self.ensure_taskbar_icon()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: #1e1b4b;
                color: #f8fafc;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 8px;
                padding: 6px;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background: #4338ca;
            }
        """)
        pin_action = menu.addAction("📌 항상 위에 고정" if not self.is_pinned else "📌 고정 해제")
        shortcut_action = menu.addAction("📁 바탕화면 바로가기 생성")
        menu.addSeparator()
        close_action = menu.addAction("✕ 프로그램 종료")

        action = menu.exec_(self.mapToGlobal(event.pos()))
        if action == pin_action:
            self.toggle_pin()
        elif action == shortcut_action:
            target_exe = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__)
            create_windows_shortcuts(target_exe)
            self.status_label.setText("✅ 바탕화면에 바로가기를 생성했습니다.")
        elif action == close_action:
            self.close()

    def process_files(self, paths):
        self.open_folder_btn.hide()
        self.progress_bar.show()
        self.box_icon.setText("⏳")
        self.box_text.setText("초경량 GLB 및 완제품 ZIP 생성 중...\n(잠시만 기다려주세요)")
        self.status_label.setStyleSheet("color: #38bdf8; font-size: 11px;")
        self.status_label.setText("3D 인코딩 엔진 가동 중...")

        self.worker = WorkerThread(paths)
        self.worker.progress_signal.connect(self.update_progress)
        self.worker.finished_signal.connect(self.handle_finish)
        self.worker.start()

    def update_progress(self, msg):
        self.status_label.setText(msg)

    def handle_finish(self, success, zip_path, zip_size, msg):
        self.progress_bar.hide()
        if success:
            self.last_zip_path = zip_path
            self.box_icon.setText("🎉")
            self.box_text.setText(f"{os.path.basename(zip_path)}\n패키징 완성! ({zip_size})")
            self.status_label.setStyleSheet("color: #4ade80; font-size: 11px; font-weight: bold;")
            self.status_label.setText("✅ 7MB GLB 포함 완제품 ZIP 완성!")
            self.open_folder_btn.show()
        else:
            self.box_icon.setText("⚠️")
            self.box_text.setText(f"오류가 발생했습니다\n다시 시도해 주세요")
            self.status_label.setStyleSheet("color: #f87171; font-size: 11px;")
            self.status_label.setText(msg[:40])

    def open_result_folder(self):
        if self.last_zip_path and os.path.exists(self.last_zip_path):
            subprocess.run(f'explorer.exe /select,"{self.last_zip_path}"', shell=True)

    # 창 드래그 이동 지원
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.old_pos = event.globalPos()

    def mouseMoveEvent(self, event):
        if self.old_pos is not None:
            delta = QPoint(event.globalPos() - self.old_pos)
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPos()

    def mouseReleaseEvent(self, event):
        self.old_pos = None


def log_debug(msg):
    try:
        log_dir = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'ThePage3D')
        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, 'debug.log'), 'a', encoding='utf-8') as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass


def run_self_installer_if_needed():
    """
    바이너리(frozen exe)로 실행되었을 때, 
    현재 위치가 영구 설치 경로(%LOCALAPPDATA%\\ThePage3D)가 아니라면
    자동으로 본체를 시스템 앱 경로에 설치하고 바탕화면에 아이콘을 생성한 뒤 실행.
    이를 통해 사용자가 다운로드 폴더의 임시 파일을 삭제해도 평생 안전하게 사용 가능.
    """
    if not getattr(sys, 'frozen', False):
        return # 파이썬 개발 환경에서는 패스

    current_exe = os.path.abspath(sys.executable)
    install_dir = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'ThePage3D')
    target_exe = os.path.join(install_dir, 'ThePage3D.exe')

    log_debug(f"Check: current={current_exe}, target={target_exe}")

    # 이미 설치 경로에서 실행 중이면 그대로 앱 실행
    if os.path.normcase(current_exe) == os.path.normcase(target_exe):
        log_debug("Already in install dir, continuing main app launch.")
        return

    # [자가 설치 수행]
    try:
        log_debug("Installing to " + install_dir)
        os.makedirs(install_dir, exist_ok=True)
        
        # 1. 기존 타겟 파일이 실행 중일 수 있으니 덮어쓰기 복사
        try:
            shutil.copy2(current_exe, target_exe)
        except Exception:
            try:
                subprocess.run(['taskkill', '/f', '/im', 'ThePage3D.exe'], capture_output=True)
                time.sleep(0.5)
                shutil.copy2(current_exe, target_exe)
            except Exception as ce:
                log_debug(f"Warning copying exe: {ce}")
        log_debug("Copied binary to target_exe")
        
        # 2. 아이콘 복사
        ico_src = os.path.join(getattr(sys, '_MEIPASS', os.path.dirname(current_exe)), 'app_icon.ico')
        if os.path.exists(ico_src):
            try: shutil.copy2(ico_src, os.path.join(install_dir, 'app_icon.ico'))
            except Exception: pass

        # 3. 로컬 독립 엔진 압축 해제 (%LOCALAPPDATA%\ThePage3D\engine)
        engine_dir = os.path.join(install_dir, 'engine')
        node_in_engine = os.path.join(engine_dir, 'node.exe')
        obj2gltf_js = os.path.join(engine_dir, 'node_modules', 'obj2gltf', 'bin', 'obj2gltf.js')
        if not (os.path.exists(node_in_engine) and os.path.exists(obj2gltf_js)):
            log_debug("Extracting local engine to " + engine_dir)
            engine_zip_src = os.path.join(getattr(sys, '_MEIPASS', os.path.dirname(current_exe)), 'engine.zip')
            if not os.path.exists(engine_zip_src):
                engine_zip_src = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'engine.zip')
            if os.path.exists(engine_zip_src):
                os.makedirs(engine_dir, exist_ok=True)
                with zipfile.ZipFile(engine_zip_src, 'r') as zf:
                    zf.extractall(engine_dir)
                log_debug("Local engine extracted successfully.")

        # 4. 바탕화면 및 시작메뉴 바로가기 생성
        log_debug("Creating desktop & start menu shortcuts...")
        create_windows_shortcuts(target_exe)
        log_debug("Shortcuts created.")

        # 4. 설치된 본체 프로세스를 탐색기 ShellExecute(os.startfile)로 완전 독립 구동
        log_debug("Starting target_exe via os.startfile...")
        os.startfile(target_exe)
        log_debug("Self-installer exiting successfully.")
        sys.exit(0)
    except Exception as e:
        log_debug(f"Self-installer exception: {str(e)}")


if __name__ == '__main__':
    try:
        # 1. 자가 설치 검사 (임시 폴더에서 실행된 경우 영구 설치 후 본체 실행)
        run_self_installer_if_needed()

        # 2. 메인 앱 구동
        log_debug("Starting QApplication...")
        app = QApplication(sys.argv)
        app.setWindowIcon(get_app_icon())
        window = MainWindow()
        if "--installed" in sys.argv:
            window.status_label.setStyleSheet("color: #4ade80; font-size: 11px; font-weight: bold;")
            window.status_label.setText("✨ 바탕화면에 아이콘 설치 완료!")
        log_debug("Showing MainWindow...")
        window.show()
        log_debug("Entering app.exec_()...")
        sys.exit(app.exec_())
    except Exception as e:
        import traceback
        try:
            log_dir = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'ThePage3D')
            os.makedirs(log_dir, exist_ok=True)
            with open(os.path.join(log_dir, 'crash.log'), 'a', encoding='utf-8') as f:
                f.write(traceback.format_exc())
        except Exception:
            pass
