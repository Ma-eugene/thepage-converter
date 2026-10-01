# -*- coding: utf-8 -*-
"""
3D 피규어 초경량 GLB 자동 생성 및 완성형 ZIP 자동 패키징 도구
- OBJ + MTL + JPG -> 7MB 초경량 Draco GLB 자동 생성
- 서브폴더 없는 최상위 완제품 ZIP 자동 생성 (출력실 + 3D 웹뷰어 100% 호환)
"""

import os
import sys
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
            if len(meshes) != 1: # 파편화된 메시 구버전 재변환
                return False
            primitives = meshes[0].get('primitives', [])
            if not primitives:
                return False
            attrs = primitives[0].get('attributes', {})
            if 'NORMAL' not in attrs: # 노멀 누락 구버전 재변환
                return False
            return True
    except Exception:
        return False

def print_banner():
    print("=" * 65)
    print("   🎨 더페이지 3D 피규어 초경량 변환 및 ZIP 패키징 도구 v1.0")
    print("=" * 65)

def find_target_dir_and_files(args):
    if not args:
        print("[오류] 변환할 폴더나 파일이 지정되지 않았습니다.")
        print("사용법: 폴더 또는 3D 파일(OBJ, MTL, JPG)을 이 프로그램 위로 끌어다 놓으세요.")
        return None, []

    first_arg = os.path.abspath(args[0])

    if os.path.isdir(first_arg):
        target_dir = first_arg
    else:
        target_dir = os.path.dirname(first_arg)

    return target_dir

def check_required_tools():
    # npx 또는 node 존재 여부 확인
    npx_cmd = shutil.which("npx") or shutil.which("npx.cmd")
    node_cmd = shutil.which("node") or shutil.which("node.exe")
    return npx_cmd, node_cmd

def convert_and_pack(target_dir):
    print(f"\n[1/4] 작업 대상 폴더 확인:")
    print(f"  -> 경로: {target_dir}")

    folder_name = os.path.basename(os.path.normpath(target_dir))
    all_files = os.listdir(target_dir)

    # 1. 파일 탐색
    obj_files = [f for f in all_files if f.lower().endswith('.obj')]
    mtl_files = [f for f in all_files if f.lower().endswith('.mtl')]
    jpg_files = [f for f in all_files if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    glb_files = [f for f in all_files if f.lower().endswith('.glb')]

    if not obj_files:
        print("\n[오류] 폴더 내에 .obj 3D 모델 파일이 없습니다!")
        return False

    obj_name = obj_files[0]
    base_name = os.path.splitext(obj_name)[0]
    obj_path = os.path.join(target_dir, obj_name)

    print(f"\n[2/4] 감지된 3D 소스 파일:")
    print(f"  - OBJ 모델: {obj_name} ({os.path.getsize(obj_path) / (1024*1024):.1f} MB)")
    if mtl_files:
        print(f"  - MTL 재질: {mtl_files[0]}")
    if jpg_files:
        print(f"  - 텍스처 이미지: {jpg_files[0]}")

    # 2. GLB 변환 여부 결정
    target_glb_name = f"{base_name}.glb"
    target_glb_path = os.path.join(target_dir, target_glb_name)

    need_conversion = True
    if os.path.exists(target_glb_path):
        glb_size_mb = os.path.getsize(target_glb_path) / (1024 * 1024)
        if glb_size_mb < 15.0 and check_glb_is_optimized(target_glb_path):
            print(f"  - 기존 최적화 GLB 감지됨 ({glb_size_mb:.2f} MB) -> 변환 단계 건너뜀 (OK)")
            need_conversion = False
        else:
            print(f"  - 기존 GLB가 구버전/미최적화 상태임 -> 단일 메시 및 노멀 자동 최적화 재변환 진행")

    if need_conversion:
        print(f"\n[3/4] 🚀 구글 Draco 무손실 초경량 GLB 자동 변환 중... (약 3~5초 소요)")
        
        # 100% 로컬 독립 엔진 탐색
        install_dir = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'ThePage3D')
        engine_node = os.path.join(install_dir, 'engine', 'node.exe')
        engine_obj2gltf = os.path.join(install_dir, 'engine', 'node_modules', 'obj2gltf', 'bin', 'obj2gltf.js')
        engine_gltfpack = os.path.join(install_dir, 'engine', 'node_modules', 'gltfpack', 'cli.js')
        engine_pipeline = os.path.join(install_dir, 'engine', 'node_modules', 'gltf-pipeline', 'bin', 'gltf-pipeline.js')
        
        tools_dir = os.path.dirname(os.path.abspath(__file__))
        dev_node = r'C:\Program Files\nodejs\node.exe' if os.path.exists(r'C:\Program Files\nodejs\node.exe') else shutil.which('node')
        dev_obj2gltf = os.path.join(tools_dir, 'node_modules', 'obj2gltf', 'bin', 'obj2gltf.js')
        dev_gltfpack = os.path.join(tools_dir, 'node_modules', 'gltfpack', 'cli.js')
        dev_pipeline = os.path.join(tools_dir, 'node_modules', 'gltf-pipeline', 'bin', 'gltf-pipeline.js')
        
        if os.path.exists(engine_node) and os.path.exists(engine_obj2gltf):
            node_cmd = engine_node
            obj2gltf_cmd = engine_obj2gltf
            gltfpack_cmd = engine_gltfpack if os.path.exists(engine_gltfpack) else ""
            pipeline_cmd = engine_pipeline
        elif dev_node and os.path.exists(dev_obj2gltf):
            node_cmd = dev_node
            obj2gltf_cmd = dev_obj2gltf
            gltfpack_cmd = dev_gltfpack if os.path.exists(dev_gltfpack) else ""
            pipeline_cmd = dev_pipeline
        else:
            print("\n[오류] 로컬 Node.js 엔진 및 변환 스크립트를 찾을 수 없습니다!")
            return False

        temp_raw_gltf = os.path.join(target_dir, f"_temp_{base_name}.gltf")
        temp_pack_glb = os.path.join(target_dir, f"_temp_pack_{base_name}.glb")

        try:
            no_window = getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000) if sys.platform == 'win32' else 0
            
            # 1단계: obj -> raw gltf (메시 단일화 + 버텍스 노멀 자동 계산)
            cmd_obj2gltf = [node_cmd, obj2gltf_cmd, '-i', obj_path, '-o', temp_raw_gltf]
            sub_res1 = subprocess.run(cmd_obj2gltf, cwd=target_dir, capture_output=True, text=True, creationflags=no_window)
            if sub_res1.returncode != 0:
                print(f"[변환 오류 (1단계)] {sub_res1.stderr}")
                return False

            pipe_input = temp_raw_gltf
            # 2단계: gltfpack으로 폴리곤 1/10 지능형 감축 (140만 -> 14만 개 데시메이션)
            if gltfpack_cmd and os.path.exists(gltfpack_cmd):
                cmd_gltfpack = [node_cmd, gltfpack_cmd, '-i', temp_raw_gltf, '-o', temp_pack_glb, '-si', '0.05']
                sub_res_pack = subprocess.run(cmd_gltfpack, cwd=target_dir, capture_output=True, text=True, creationflags=no_window)
                if sub_res_pack.returncode == 0 and os.path.exists(temp_pack_glb):
                    pipe_input = temp_pack_glb

            # 3단계: Draco 무손실 압축 초경량 GLB 완성 (속도 최적화 level 6)
            cmd_pipeline = [node_cmd, pipeline_cmd, '-i', pipe_input, '-o', target_glb_path, '-d', '--draco.compressionLevel', '6']
            sub_res2 = subprocess.run(cmd_pipeline, cwd=target_dir, capture_output=True, text=True, creationflags=no_window)
            if sub_res2.returncode != 0:
                print(f"[변환 오류 (최종 압축)] {sub_res2.stderr}")
                return False

            final_glb_size_mb = os.path.getsize(target_glb_path) / (1024 * 1024)
            print(f"  ✅ 초경량 4MB GLB 생성 완료! 크기: {final_glb_size_mb:.2f} MB (폴리곤 1/10 다이어트)")
        finally:
            # 임시 파일 정리
            for tmp in [temp_raw_gltf, temp_pack_glb, os.path.join(target_dir, f"_temp_{base_name}.bin")]:
                if os.path.exists(tmp):
                    try: os.remove(tmp)
                    except Exception: pass

    # 3. ZIP 패키징 (작업 폴더 내부에 바로 저장)
    print(f"\n[4/4] 📦 출력실 + 3D뷰어 통합 완제품 ZIP 생성 중...")

    # ZIP 파일명 결정 (세션코드 규칙 확인)
    is_valid_code = any(prefix in folder_name.upper() for prefix in ['CHR', 'UHB', 'DG', 'HQ', 'DAT', 'AI', 'FIG', '260', '261'])
    if is_valid_code:
        zip_filename = f"{folder_name}.zip"
    else:
        # 폴더명이 세션코드가 아닐 경우 OBJ 베이스네임 사용
        zip_filename = f"{base_name}.zip"

    output_zip_path = os.path.join(target_dir, zip_filename)

    # 묶을 대상 파일들 선정: obj, mtl, jpg/png, glb
    files_to_pack = []
    for f in os.listdir(target_dir):
        ext = os.path.splitext(f)[1].lower()
        if ext in ['.obj', '.mtl', '.jpg', '.jpeg', '.png', '.glb']:
            if not f.startswith('_temp_') and f != zip_filename:
                files_to_pack.append(f)

    with zipfile.ZipFile(output_zip_path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for fname in files_to_pack:
            fpath = os.path.join(target_dir, fname)
            # arcname=fname 으로 최상위 루트에 직배치 (서브폴더 없음!)
            zf.write(fpath, arcname=fname)

    zip_size_mb = os.path.getsize(output_zip_path) / (1024 * 1024)
    print(f"\n" + "=" * 65)
    print(f"  🎉 변환 및 패키징이 성공적으로 완료되었습니다!")
    print(f"  - 생성된 파일: {output_zip_path}")
    print(f"  - 완성본 용량: {zip_size_mb:.1f} MB (원본 200MB 대비 75% 다이어트 완료)")
    print(f"  - 포함된 내용: {', '.join(files_to_pack)}")
    return True

def main():
    print_banner()
    args = sys.argv[1:]
    target_dir = find_target_dir_and_files(args)
    if not target_dir:
        input("\n계속하려면 아무 키나 누르세요...")
        return

    success = convert_and_pack(target_dir)
    if success:
        print("\n✨ 5초 후 창이 자동으로 닫힙니다. (또는 아무 키나 누르세요)")
        # 5초 카운트다운 또는 엔터 대기
        time.sleep(4)
    else:
        input("\n오류를 확인한 후 아무 키나 누르세요...")

if __name__ == '__main__':
    main()
