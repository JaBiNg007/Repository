from flask import Flask, render_template, request
import matplotlib

matplotlib.use('Agg')  # สำคัญ: ทำให้ Matplotlib วาดรูปเป็นข้อมูล ไม่ต้องเปิดหน้าต่าง GUI
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.font_manager as fm  # เพิ่ม: สำหรับจัดการฟอนต์ใน Matplotlib

# ตั้งค่าฟอนต์สำหรับ Matplotlib (ตัวอย่าง)
# เพื่อลด Warning และพยายามใช้ฟอนต์ที่ Render มี (ระบบ Linux)
plt.rcParams['font.family'] = ['DejaVu Sans', 'sans-serif'] 
# หากต้องการลองฟอนต์ไทยบางตัวที่อาจมีใน Linux Server (แต่ไม่การันตีว่า Render มีติดตั้งอยู่):
# plt.rcParams['font.family'] = ['TH Sarabun New', 'Loma', 'Norasi', 'Tlwg Typo', 'sans-serif']

import numpy as np
import io
import base64
import random
import math
import hashlib


# --- คลาสและฟังก์ชันหลักของโปรแกรมจัดวางพื้นที่ ---
class Activity:
    def __init__(self, name, required_area, possible_dimensions):
        self.name = name
        self.required_area = required_area
        self.possible_dimensions = possible_dimensions
        self.placed_dim = None
        self.position = None
        self.color = None

    def __repr__(self):
        return f"{self.name}({self.placed_dim[0]}x{self.placed_dim[1]})" if self.placed_dim else f"{self.name}(Area:{self.required_area})"


def get_possible_dimensions_for_area(area):
    dimensions = []
    for i in range(1, int(math.sqrt(area)) + 1):
        if area % i == 0:
            w1 = i
            h1 = area // i
            dimensions.append((w1, h1))
            if w1 != h1:
                dimensions.append((h1, w1))
    return sorted(list(set(dimensions)))


def create_board(width, height):
    return np.full((height, width), '.', dtype='<U10')


def can_place(board, width, height, x, y):
    board_h, board_w = board.shape
    if x < 0 or y < 0 or x + width > board_w or y + height > board_h:
        return False
    for r in range(y, y + height):
        for c in range(x, x + width):
            if board[r, c] != '.':
                return False
    return True


def place_activity(board, activity, x, y, width, height):
    for r in range(y, y + height):
        for c in range(x, x + width):
            board[r, c] = activity.name
    activity.placed_dim = (width, height)
    activity.position = (x, y)
    return True


def calculate_layout_fingerprint(placed_activities_info):
    fingerprint_data = []
    sorted_info = sorted(placed_activities_info,
                         key=lambda info: (info['position'][0], info['position'][1], info['placed_dimensions'][0],
                                           info['placed_dimensions'][1], info['name']))

    for info in sorted_info:
        fingerprint_data.append(
            (info['name'], info['placed_dimensions'][0], info['placed_dimensions'][1], info['position'][0],
             info['position'][1])
        )
    return hashlib.sha256(str(fingerprint_data).encode('utf-8')).hexdigest()


def solve_packing_with_variety_and_rotation(board_width, board_height, activities_input_list):
    board = create_board(board_width, board_height)
    placed_activities_info = []

    current_attempt_activities = []
    for orig_activity in activities_input_list:
        new_activity = Activity(orig_activity.name, orig_activity.required_area, orig_activity.possible_dimensions)
        new_activity.color = orig_activity.color
        current_attempt_activities.append(new_activity)

    # ปรับปรุงประสิทธิภาพ: เรียงกิจกรรมตามพื้นที่มากสุดไปน้อยสุด เพื่อให้วางกิจกรรมใหญ่ก่อน (First-Fit Decreasing heuristic)
    current_attempt_activities.sort(key=lambda a: a.required_area, reverse=True) 
    # random.shuffle(current_attempt_activities) # ลบการสุ่มลำดับกิจกรรมเดิมออก

    for activity in current_attempt_activities:
        placed = False

        all_possible_orientations = []
        for dim_w, dim_h in activity.possible_dimensions:
            all_possible_orientations.append((dim_w, dim_h))
            if dim_w != dim_h:
                all_possible_orientations.append((dim_h, dim_w))

        # random.shuffle(all_possible_orientations) # ลบการสุ่มลำดับรูปทรงออก

        all_possible_positions = []
        for y in range(board_height):
            for x in range(board_width):
                all_possible_positions.append((x, y))
        # random.shuffle(all_possible_positions) # ลบการสุ่มลำดับตำแหน่งออก

        for dim_w, dim_h in all_possible_orientations:
            for x, y in all_possible_positions: # ลูปนี้จะวนจาก 0,0 ไปเรื่อยๆ อย่างเป็นระบบ
                if can_place(board, dim_w, dim_h, x, y):
                    place_activity(board, activity, x, y, dim_w, dim_h)
                    placed_activities_info.append({
                        "name": activity.name,
                        "placed_dimensions": (dim_w, dim_h),
                        "position": (x, y),
                        "color": activity.color
                    })
                    placed = True
                    break
                if placed:
                    break
            if placed:
                break

        if not placed:
            return None, None

    return board, placed_activities_info


# --- สิ้นสุดส่วนคลาสและฟังก์ชันหลัก ---

app = Flask(__name__)  # สร้าง Instance ของ Flask App


# ฟังก์ชันสำหรับแปลง Matplotlib plot เป็น Base64 image เพื่อแสดงบนเว็บ
def get_plot_as_base64_image(board_width, board_height, placed_activities_info, simulation_num, total_area_covered):
    # ปรับปรุงประสิทธิภาพ: กำหนดขนาดรูปภาพให้คงที่และเล็ก (เพื่อประหยัด RAM)
    # fig, ax = plt.subplots(1, figsize=(max(8, board_width * 0.5), max(8, board_height * 0.5))) # บรรทัดเก่า
    fig, ax = plt.subplots(1, figsize=(8, 8)) # เปลี่ยนเป็นขนาดคงที่ 8x8 (หรือ 6,6 ถ้ายัง Out of Memory)

    ax.set_facecolor('lightgray')

    ax.add_patch(patches.Rectangle((0, 0), board_width, board_height,
                                   edgecolor='black', facecolor='white', linewidth=2))

    if board_width <= 20 and board_height <= 20:
        ax.set_xticks(np.arange(0, board_width + 1, 1))
        ax.set_yticks(np.arange(0, board_height + 1, 1))
        ax.grid(which='major', color='gray', linestyle=':', linewidth=0.5)

    for info in placed_activities_info:
        x, y = info["position"]
        width, height = info["placed_dimensions"]
        name = info["name"]
        color = info["color"]

        rect = patches.Rectangle(
            (x, y),
            width,
            height,
            linewidth=1,
            edgecolor='black',
            facecolor=color,
            alpha=0.7
        )
        ax.add_patch(rect)

        text_content = f"{name}\n({width}x{height})"
        ax.text(
            x + width / 2,
            y + height / 2,
            text_content,
            ha='center',
            va='center',
            color='white',
            fontsize=min(12, max(6, (width * height) ** 0.3 * 0.8)),
            # fontweight='bold' # ลบออกเพื่อลดปัญหาฟอนต์ หรือเปลี่ยนเป็น 'normal'
        )

    ax.set_xlim(0, board_width)
    ax.set_ylim(0, board_height)
    ax.set_aspect('equal', adjustable='box')

    plt.gca().invert_yaxis()

    plt.title(
        f'Simulation #{simulation_num}: Board {board_width}x{board_height} | Covered: {total_area_covered} ตร.หน่วย')
    plt.xlabel('ความกว้าง')
    plt.ylabel('ความยาว')

    # บันทึก plot ลงใน object หน่วยความจำ และเข้ารหัสเป็น base64
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)  # ปิด figure เพื่อไม่ให้ใช้หน่วยความจำเกินจำเป็น

    image_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    return image_base64


# กำหนด Route สำหรับหน้าแรกของเว็บ "/"
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':  # ถ้าเป็นการส่งข้อมูลจากฟอร์ม (Submit)
        try:
            # ดึงข้อมูลจากฟอร์มที่ผู้ใช้กรอก
            board_width = int(request.form['board_width'])
            board_height = int(request.form['board_height'])
            num_activities = int(request.form['num_activities'])
            num_simulations = int(request.form['num_simulations'])

            # ตรวจสอบความถูกต้องของข้อมูลเบื้องต้น
            if board_width <= 0 or board_height <= 0 or num_activities <= 0 or num_simulations <= 0:
                return render_template('index.html', error="ค่าทั้งหมดต้องเป็นจำนวนเต็มบวก กรุณาลองใหม่")

            original_activities_list = []
            total_required_area = 0
            # กำหนด Pool สีสำหรับกิจกรรมต่างๆ (สุ่มสี)
            colors_pool = ['#FFC300', '#FF5733', '#C70039', '#900C3F', '#581845', '#4CAF50', '#2196F3', '#FF9800',
                            '#673AB7',
                            '#00BCD4', '#8BC34A', '#FFEB3B', '#795548', '#607D8B', '#E91E63', '#9C27B0', '#009688',
                            '#FFCDD2']
            random.shuffle(colors_pool)
            color_map = {}  # ใช้เก็บ Map ชื่อกิจกรรมกับสีที่ถูกกำหนดให้

            # วนลูปเพื่อดึงข้อมูลของแต่ละกิจกรรมย่อย
            for i in range(num_activities):
                activity_name = request.form[f'activity_name_{i}']
                required_area = int(request.form[f'required_area_{i}'])

                if not activity_name or required_area <= 0:
                    return render_template('index.html',
                                           error="ชื่อพื้นที่ย่อยต้องไม่ว่างเปล่าและขนาดพื้นที่ต้องเป็นจำนวนบวก")

                if activity_name not in color_map:  # กำหนดสีให้กิจกรรมที่ไม่เคยมีสีมาก่อน
                    color_map[activity_name] = colors_pool[len(color_map) % len(colors_pool)]

                possible_dims = get_possible_dimensions_for_area(required_area)
                activity_obj = Activity(activity_name, required_area, possible_dims)
                activity_obj.color = color_map[activity_name]
                original_activities_list.append(activity_obj)
                total_required_area += required_area

            if not original_activities_list:
                return render_template('index.html', error="ไม่มีกิจกรรมให้จัดวาง")

            # เตรียมตัวแปรสำหรับเก็บผลลัพธ์การจำลอง
            results = []
            successful_simulations_count = 0
            generated_fingerprints = set()  # ใช้เก็บ Fingerprint เพื่อป้องกันการแสดงรูปแบบที่ซ้ำกัน
            simulation_attempt_num = 0

            # กำหนดจำนวนครั้งที่พยายามสูงสุด เพื่อป้องกันการวนลูปไม่รู้จบหากหาคำตอบยาก
            MAX_ATTEMPTS = min(num_simulations * 50, 500) # ปรับปรุงประสิทธิภาพ: จำกัดจำนวนครั้งที่พยายาม

            # เริ่มวนลูปเพื่อสร้างรูปแบบการจัดวางที่ไม่ซ้ำกันตามจำนวนที่ต้องการ
            while successful_simulations_count < num_simulations and simulation_attempt_num < MAX_ATTEMPTS:
                simulation_attempt_num += 1

                # สร้าง Activity object ชุดใหม่สำหรับแต่ละการพยายาม เพื่อให้สามารถสุ่มลำดับการจัดวางและตำแหน่งได้ใหม่ทุกครั้ง
                current_simulation_activities = []
                for orig_activity in original_activities_list:
                    new_activity = Activity(orig_activity.name, orig_activity.required_area,
                                            orig_activity.possible_dimensions)
                    new_activity.color = orig_activity.color
                    current_simulation_activities.append(new_activity)

                # เรียกใช้ฟังก์ชันหลักในการแก้ปัญหาการจัดวาง
                final_board_grid, placed_info = solve_packing_with_variety_and_rotation(board_width, board_height,
                                                                                       current_simulation_activities)

                if final_board_grid is not None:  # ถ้าจัดวางสำเร็จ
                    current_layout_fingerprint = calculate_layout_fingerprint(placed_info)

                    if current_layout_fingerprint not in generated_fingerprints:  # ตรวจสอบว่าเป็นรูปแบบที่ไม่ซ้ำกันหรือไม่
                        generated_fingerprints.add(current_layout_fingerprint)
                        successful_simulations_count += 1  # นับเพิ่มสำหรับรูปแบบที่ไม่ซ้ำกัน

                        # สร้างรูปภาพ Matplotlib และแปลงเป็น Base64 string
                        plot_image = get_plot_as_base64_image(board_width, board_height, placed_info,
                                                              successful_simulations_count, total_required_area)

                        # เตรียมรายละเอียดกิจกรรมเพื่อแสดงบนหน้าเว็บ
                        activity_details = []
                        for info in placed_info:
                            activity_details.append(
                                f"กิจกรรม {info['name']}: จัดวางในขนาด {info['placed_dimensions'][0]}x{info['placed_dimensions'][1]} (พื้นที่ {info['placed_dimensions'][0] * info['placed_dimensions'][1]} ตร.หน่วย) ที่ตำแหน่ง (x={info['position'][0]}, y={info['position'][1]})"
                            )

                        # เพิ่มผลลัพธ์ของรูปแบบนี้เข้าไปใน List
                        results.append({
                            'simulation_number': successful_simulations_count,
                            'attempt_number': simulation_attempt_num,
                            'plot_image': plot_image,
                            'activity_details': activity_details
                        })

                # ออกจากลูปหากได้จำนวนรูปแบบที่ไม่ซ้ำกันครบตามต้องการแล้ว
                if successful_simulations_count >= num_simulations:
                    break

            # ส่งข้อมูลทั้งหมดไปแสดงผลในหน้า results.html
            return render_template('results.html',
                                   results=results,
                                   total_attempts=simulation_attempt_num,
                                   total_unique=len(generated_fingerprints),
                                   board_width=board_width,
                                   board_height=board_height,
                                   total_required_area=total_required_area)

        except Exception as e:  # ดักจับข้อผิดพลาดทั่วไป
            # หากเกิดข้อผิดพลาด ให้กลับไปหน้าแรกพร้อมแสดงข้อความผิดพลาด
            return render_template('index.html', error=f"เกิดข้อผิดพลาด: {e}. กรุณาตรวจสอบข้อมูลที่ป้อน")

    else:  # ถ้าเป็นการเข้าเว็บครั้งแรก (GET request)
        # แสดงหน้าฟอร์มเริ่มต้น (index.html)
        return render_template('index.html')


# ส่วนนี้จะรันเมื่อเราเรียกใช้ไฟล์ app.py โดยตรง
if __name__ == '__main__':
    app.run(
        debug=False)  # <--- เปลี่ยนจาก debug=True เป็น debug=False สำหรับ Production