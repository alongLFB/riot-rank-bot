import json

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ME Flex Top 30 玩家游戏时间统计</title>
    <!-- 引入 html2pdf.js 用于导出 PDF -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
    <!-- 引入 html2canvas 用于导出图片 -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
    <style>
        :root {
            --bg-color: #0f172a;
            --panel-bg: rgba(30, 41, 59, 0.7);
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --accent: #3b82f6;
            --accent-hover: #2563eb;
            --bar-color: linear-gradient(90deg, #3b82f6, #8b5cf6);
            --border-color: rgba(255, 255, 255, 0.1);
        }
        
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }

        body {
            background-color: var(--bg-color);
            background-image: 
                radial-gradient(at 0% 0%, rgba(59, 130, 246, 0.15) 0px, transparent 50%),
                radial-gradient(at 100% 100%, rgba(139, 92, 246, 0.15) 0px, transparent 50%);
            background-attachment: fixed;
            color: var(--text-main);
            min-height: 100vh;
            padding: 2rem;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
        }

        .header {
            text-align: center;
            margin-bottom: 3rem;
            animation: fadeInDown 0.8s ease-out;
        }

        .header h1 {
            font-size: 2.5rem;
            font-weight: 800;
            background: linear-gradient(to right, #60a5fa, #c084fc);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.5rem;
        }

        .header p {
            color: var(--text-muted);
            font-size: 1.1rem;
        }

        .actions {
            display: flex;
            justify-content: center;
            gap: 1rem;
            margin-bottom: 2rem;
        }

        button {
            background: var(--panel-bg);
            border: 1px solid var(--border-color);
            color: var(--text-main);
            padding: 0.75rem 1.5rem;
            border-radius: 0.75rem;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            backdrop-filter: blur(10px);
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        button:hover {
            background: var(--accent);
            border-color: var(--accent);
            transform: translateY(-2px);
            box-shadow: 0 10px 15px -3px rgba(59, 130, 246, 0.3);
        }

        .glass-panel {
            background: var(--panel-bg);
            backdrop-filter: blur(12px);
            border: 1px solid var(--border-color);
            border-radius: 1.5rem;
            padding: 2rem;
            margin-bottom: 2rem;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
            animation: fadeIn 1s ease-out;
        }

        .section-title {
            font-size: 1.5rem;
            font-weight: 700;
            margin-bottom: 1.5rem;
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }

        .section-title::before {
            content: '';
            display: block;
            width: 4px;
            height: 1.5rem;
            background: var(--bar-color);
            border-radius: 2px;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }

        .stat-card {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid var(--border-color);
            border-radius: 1rem;
            padding: 1.5rem;
            text-align: center;
            transition: transform 0.3s ease;
        }

        .stat-card:hover {
            transform: translateY(-5px);
            background: rgba(255, 255, 255, 0.05);
        }

        .stat-value {
            font-size: 2rem;
            font-weight: 800;
            color: #60a5fa;
            margin-bottom: 0.5rem;
        }

        .stat-label {
            color: var(--text-muted);
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        table {
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
            margin-top: 1rem;
        }

        th, td {
            padding: 1rem;
            text-align: left;
            border-bottom: 1px solid var(--border-color);
        }

        th {
            color: var(--text-muted);
            font-weight: 600;
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            position: sticky;
            top: 0;
            background: var(--bg-color);
            z-index: 10;
        }

        tr:last-child td {
            border-bottom: none;
        }

        tbody tr {
            transition: background-color 0.2s ease;
        }

        tbody tr:hover {
            background-color: rgba(255, 255, 255, 0.03);
        }

        .progress-wrapper {
            width: 100%;
            height: 8px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 4px;
            overflow: hidden;
            margin-top: 0.5rem;
        }

        .progress-bar {
            height: 100%;
            background: var(--bar-color);
            border-radius: 4px;
            transition: width 1s cubic-bezier(0.4, 0, 0.2, 1);
        }

        .player-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid var(--border-color);
        }
        
        .player-name {
            font-size: 1.25rem;
            font-weight: 700;
            color: #c084fc;
        }

        .player-lp {
            background: rgba(139, 92, 246, 0.2);
            color: #d8b4fe;
            padding: 0.25rem 0.75rem;
            border-radius: 1rem;
            font-size: 0.875rem;
            font-weight: 600;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }

        @keyframes fadeInDown {
            from { opacity: 0; transform: translateY(-20px); }
            to { opacity: 1; transform: translateY(0); }
        }

        /* 导出时的样式调整 (强制浅色高对比度主题) */
        .exporting .actions {
            display: none !important;
        }
        .exporting {
            background: #ffffff !important;
            color: #000000 !important;
            padding: 20px !important;
            background-image: none !important;
        }
        .exporting .glass-panel {
            background: #f8fafc !important;
            border: 1px solid #e2e8f0 !important;
            color: #0f172a !important;
            box-shadow: none !important;
            border-radius: 0 !important;
            margin-bottom: 2rem !important;
            break-inside: avoid;
        }
        .exporting .text-muted, .exporting th, .exporting .stat-label, .exporting .header p {
            color: #475569 !important;
        }
        .exporting .player-name, .exporting .stat-value, .exporting .header h1, .exporting td, .exporting p {
            background: none !important;
            -webkit-text-fill-color: #0f172a !important;
            color: #0f172a !important;
        }
        .exporting .player-lp {
            background: #e2e8f0 !important;
            color: #0f172a !important;
        }
        .exporting td {
            border-bottom-color: #e2e8f0 !important;
        }
        .exporting th {
            background: #f8fafc !important;
        }
    </style>
</head>
<body>
    <div class="container" id="report-content">
        <div class="header">
            <h1>ME Flex 活跃时间洞察报告</h1>
            <p id="generated-time">统计生成时间: --</p>
        </div>

        <div class="actions" data-html2canvas-ignore>
            <button onclick="exportImage()">
                <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"></path></svg>
                导出为长图
            </button>
            <button onclick="exportPDF()">
                <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
                导出为 PDF
            </button>
        </div>

        <div class="glass-panel">
            <h2 class="section-title">总体统计汇总</h2>
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value" id="global-matches">0</div>
                    <div class="stat-label">总分析对局数</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="peak-hour">--:--</div>
                    <div class="stat-label">全服最活跃时段 (UAE)</div>
                </div>
            </div>
            
            <table>
                <thead>
                    <tr>
                        <th>时间段 (UAE)</th>
                        <th>对局数量</th>
                        <th style="width: 50%;">占比</th>
                    </tr>
                </thead>
                <tbody id="global-table-body">
                    <!-- 动态插入 -->
                </tbody>
            </table>
        </div>

        <div id="players-container">
            <!-- 玩家数据动态插入 -->
        </div>
    </div>

    <script>
        // 这是占位符，Python 会用真实数据替换这里
        const REPORT_DATA = __DATA_PLACEHOLDER__;

        function renderData() {
            if (!REPORT_DATA || !REPORT_DATA.players) return;

            document.getElementById('generated-time').textContent = `统计生成时间: ${REPORT_DATA.generated_at}`;
            document.getElementById('global-matches').textContent = REPORT_DATA.global_total_matches;

            // Render Global Table
            const globalTbody = document.getElementById('global-table-body');
            let maxGlobalCount = 0;
            let peakHourStr = "--:--";
            
            for (let i = 0; i < 24; i++) {
                const count = REPORT_DATA.global_play_hours[i] || 0;
                if (count > maxGlobalCount) {
                    maxGlobalCount = count;
                    peakHourStr = `${i.toString().padStart(2, '0')}:00`;
                }
            }
            document.getElementById('peak-hour').textContent = peakHourStr;

            for (let i = 0; i < 24; i++) {
                const count = REPORT_DATA.global_play_hours[i] || 0;
                if(count === 0) continue; // 可以选择隐藏 0 场次的时段
                const pct = REPORT_DATA.global_total_matches > 0 ? (count / REPORT_DATA.global_total_matches * 100).toFixed(1) : 0;
                
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${i.toString().padStart(2, '0')}:00 - ${(i+1).toString().padStart(2, '0')}:00</td>
                    <td><span style="color: #60a5fa; font-weight: 600;">${count}</span> 场</td>
                    <td>
                        <div style="display: flex; justify-content: space-between; margin-bottom: 0.25rem;">
                            <span>${pct}%</span>
                        </div>
                        <div class="progress-wrapper">
                            <div class="progress-bar" style="width: 0%" data-width="${pct}%"></div>
                        </div>
                    </td>
                `;
                globalTbody.appendChild(tr);
            }

            // Render Players
            const playersContainer = document.getElementById('players-container');
            REPORT_DATA.players.forEach(p => {
                const panel = document.createElement('div');
                panel.className = 'glass-panel';
                
                let tbodyHtml = '';
                if (p.total_matches > 0) {
                    for (let i = 0; i < 24; i++) {
                        const count = p.play_hours[i] || 0;
                        if (count > 0) {
                            const pct = (count / p.total_matches * 100).toFixed(1);
                            tbodyHtml += `
                                <tr>
                                    <td>${i.toString().padStart(2, '0')}:00 - ${(i+1).toString().padStart(2, '0')}:00</td>
                                    <td>${count} 场</td>
                                    <td>
                                        <div style="display: flex; justify-content: space-between; margin-bottom: 0.25rem;">
                                            <span>${pct}%</span>
                                        </div>
                                        <div class="progress-wrapper">
                                            <div class="progress-bar" style="width: 0%" data-width="${pct}%"></div>
                                        </div>
                                    </td>
                                </tr>
                            `;
                        }
                    }
                } else {
                    tbodyHtml = `<tr><td colspan="3" style="text-align:center; color: var(--text-muted);">暂无近期对局数据</td></tr>`;
                }

                panel.innerHTML = `
                    <div class="player-header">
                        <div class="player-name">[${p.idx}/${p.total_top || 30}] ${p.riot_id}</div>
                        <div class="player-lp">${p.league_points} LP</div>
                    </div>
                    <p style="color: var(--text-muted); margin-bottom: 1rem;">近期分析对局：<span style="color: #fff; font-weight: 600;">${p.total_matches}</span> 场</p>
                    <table>
                        <thead>
                            <tr>
                                <th>时间段 (UAE)</th>
                                <th>对局数量</th>
                                <th style="width: 50%;">占比</th>
                            </tr>
                        </thead>
                        <tbody>${tbodyHtml}</tbody>
                    </table>
                `;
                playersContainer.appendChild(panel);
            });

            // Trigger animations
            setTimeout(() => {
                document.querySelectorAll('.progress-bar').forEach(bar => {
                    bar.style.width = bar.getAttribute('data-width');
                });
            }, 100);
        }

        function exportImage() {
            const content = document.getElementById('report-content');
            document.body.classList.add('exporting');
            
            html2canvas(content, {
                scale: 2,
                backgroundColor: '#ffffff',
                useCORS: true,
                windowWidth: 1200
            }).then(canvas => {
                document.body.classList.remove('exporting');
                const link = document.createElement('a');
                link.download = 'ME_Flex_Report.png';
                link.href = canvas.toDataURL('image/png');
                link.click();
            }).catch(err => {
                document.body.classList.remove('exporting');
                alert("导出图片失败: " + err);
            });
        }

        function exportPDF() {
            const element = document.getElementById('report-content');
            document.body.classList.add('exporting');
            
            const opt = {
                margin:       10,
                filename:     'ME_Flex_Report.pdf',
                image:        { type: 'jpeg', quality: 0.98 },
                html2canvas:  { scale: 2, backgroundColor: '#ffffff', useCORS: true },
                jsPDF:        { unit: 'mm', format: 'a4', orientation: 'portrait' }
            };

            html2pdf().set(opt).from(element).save().then(() => {
                document.body.classList.remove('exporting');
            }).catch(err => {
                document.body.classList.remove('exporting');
                alert("导出 PDF 失败: " + err);
            });
        }

        // 初始化
        window.onload = renderData;
    </script>
</body>
</html>
"""

def generate_report_html(data_dict, output_path="flex_play_times_report.html"):
    json_str = json.dumps(data_dict, ensure_ascii=False)
    html_content = HTML_TEMPLATE.replace("__DATA_PLACEHOLDER__", json_str)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
