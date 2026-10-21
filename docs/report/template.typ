// template.typ: 高品质高校工科实验报告 Typst 模板
// 专为《数字电路与逻辑设计实验》等硬件实验报告定制，符合严肃工科课程设计报告标准规范

#let lab_report(
  title: "实验报告",
  subtitle: "",
  course: "数字电路与逻辑设计实验（下）",
  semester: "2026～2027学年第一学期",
  student_name: "__________",
  student_id: "__________",
  major_class: "__________",
  advisor: "__________",
  date: "2026年10月",
  score: "__________",
  body,
) = {
  // 页面全局设定
  set page(
    paper: "a4",
    margin: (x: 2.2cm, top: 2.3cm, bottom: 2.2cm),
    header: context {
      let p = counter(page).get().first()
      // 封面与目录不显示页眉 (封面为 0, 目录为 0)
      if p > 0 [
        #set text(size: 8.5pt, font: ("Songti SC", "STSong", "Heiti SC"), fill: rgb("#475569"))
        #grid(
          columns: (1fr, auto),
          align(left)[#course · 课程设计报告],
          align(right)[#title]
        )
        #v(-5pt)
        #line(length: 100%, stroke: 0.5pt + rgb("#94a3b8"))
      ]
    },
    footer: context {
      let p = counter(page).get().first()
      if p > 0 [
        #set text(size: 9pt, font: "Songti SC", fill: rgb("#64748b"))
        #align(center)[- #p -]
      ]
    }
  )

  // 中文字体及段落设定
  set text(
    font: ("Songti SC", "STSong"),
    size: 10pt,
    lang: "zh",
    region: "CN",
    fill: rgb("#111827"),
  )

  set par(
    justify: true,
    leading: 0.72em,
    first-line-indent: 2em,
  )

  // 严谨工科实验报告标准标题规范（无现代网页强调条、无花哨着色）
  show heading.where(level: 1): it => block(
    width: 100%,
    above: 20pt,
    below: 10pt,
  )[
    #set text(font: ("Heiti SC", "Hiragino Sans GB"), size: 14pt, weight: "bold", fill: rgb("#000000"))
    #it.body
  ]

  show heading.where(level: 2): it => block(
    width: 100%,
    above: 14pt,
    below: 7pt,
  )[
    #set text(font: ("Heiti SC", "Hiragino Sans GB"), size: 12pt, weight: "bold", fill: rgb("#111827"))
    #it.body
  ]

  show heading.where(level: 3): it => block(
    width: 100%,
    above: 10pt,
    below: 5pt,
  )[
    #set text(font: ("Heiti SC", "Hiragino Sans GB"), size: 10.5pt, weight: "bold", fill: rgb("#1f2937"))
    #it.body
  ]

  // 国家标准学术三线表规范
  set table(
    stroke: (x, y) => if y == 0 {
      (top: 1.2pt + rgb("#000000"), bottom: 0.75pt + rgb("#000000"))
    } else {
      (bottom: 0.35pt + rgb("#e5e7eb"))
    },
    fill: (col, row) => if row == 0 {
      rgb("#f9fafb")
    } else {
      none
    },
    inset: (x: 5pt, y: 4.5pt),
  )

  // 图表图题规范
  show figure.caption: it => [
    #v(4pt)
    #set text(size: 9pt, font: ("Songti SC", "STSong"), fill: rgb("#4b5563"))
    #it
  ]

  // 代码块样式：标准黑白学术 monospace 边框，无圆角
  show raw.where(block: true): it => block(
    fill: rgb("#f8fafc"),
    stroke: 0.5pt + rgb("#cbd5e1"),
    inset: (x: 7pt, y: 5.5pt),
    radius: 0pt,
    width: 100%,
    clip: true,
  )[
    #set text(size: 7.2pt, font: ("Menlo", "Courier New"))
    #it
  ]

  // 行内代码样式：正规灰底无圆角
  show raw.where(block: false): it => box(
    fill: rgb("#f1f5f9"),
    inset: (x: 2.5pt, y: 0pt),
    outset: (y: 2.5pt),
    radius: 0pt,
    baseline: 0pt,
  )[
    #set text(size: 8.5pt, font: ("Menlo", "Courier New"), fill: rgb("#000000"))
    #it
  ]

  // ==================== 封面页 ====================
  counter(page).update(0)
  
  align(center)[
    #v(1.8cm)
    #text(size: 24pt, font: "Heiti SC", weight: "bold", fill: rgb("#000000"))[#course]
    #v(1.2cm)
    #text(size: 18pt, font: "Heiti SC", weight: "bold", fill: rgb("#000000"))[#title]
    #if subtitle != "" [
      #v(0.6cm)
      #text(size: 12pt, font: "Songti SC", fill: rgb("#374151"))[#subtitle]
    ]

    #v(4.2cm)
    #align(center)[
      #block(width: 75%)[
        #set text(size: 11pt, font: "Songti SC")
        #grid(
          columns: (80pt, 1fr),
          row-gutter: 15pt,
          align: (right + horizon, left + horizon),
          [课程名称：], [#course],
          [实验学期：], [#semester],
          [专业班级：], [#major_class],
          [学生姓名：], [#student_name],
          [学生学号：], [#student_id],
          [指导教师：], [#advisor],
          [实验成绩：], [#score],
          [报告日期：], [#date],
        )
      ]
    ]
  ]

  pagebreak()

  // ==================== 目录 ====================
  block(width: 100%, below: 16pt)[
    #align(center)[
      #text(size: 15pt, font: "Heiti SC", weight: "bold", fill: rgb("#000000"))[目    录]
    ]
    #v(12pt)
    #outline(title: none, depth: 2, indent: auto)
  ]

  pagebreak()

  // 正文从第 1 页开始编号
  counter(page).update(1)

  body
}
