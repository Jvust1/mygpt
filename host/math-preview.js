import katex from '../third_party/katex/katex.mjs';

// Presentation only. Never rewrite the accepted source, hash, prompt or receipt.
export const MATH_LIMITS = Object.freeze({characters:1000, nesting:32, commands:80, formulas:16, total:8000});
const forbidden = /\\(?:def|gdef|edef|xdef|let|futurelet|newcommand|renewcommand|providecommand|expandafter|csname|noexpand|global|catcode|htmlClass|htmlId|htmlStyle|htmlData|href|url|includegraphics)\b|\^\^/;

export function canPreviewMath(latex) {
  if (typeof latex !== 'string' || !latex.trim() || latex.length > MATH_LIMITS.characters || forbidden.test(latex)) return false;
  let depth=0, commands=0;
  for (const char of latex) {
    if (char==='\\' && ++commands > MATH_LIMITS.commands) return false;
    if (char==='{' && ++depth > MATH_LIMITS.nesting) return false;
    if (char==='}' && --depth < 0) return false;
  }
  return depth===0;
}

export function renderSourceParts(target, parts) {
  const doc=target.ownerDocument, nodes=[];
  let formulas=0, total=0;
  for (const part of parts) {
    if (part.kind !== 'math') {
      const text=doc.createElement('p'); text.textContent=part.text; nodes.push(text); continue;
    }
    const figure=doc.createElement('figure'); figure.className='math-preview';
    const raw=doc.createElement('code'); raw.className='math-raw'; raw.textContent=part.latex;
    const layout=doc.createElement('div'); layout.className='math-layout';
    let rendered=false;
    if (formulas < MATH_LIMITS.formulas && total + part.latex.length <= MATH_LIMITS.total && canPreviewMath(part.latex)) {
      formulas++; total+=part.latex.length;
      try {
        // KaTeX constructs DOM nodes; source text never enters an HTML parser.
        // No shared macro object, external font sheet, URL or HTML extension.
        katex.render(part.latex,layout,{output:'mathml',displayMode:part.display===true,
          trust:false,strict:'error',throwOnError:true,maxExpand:200,maxSize:10,macros:{},globalGroup:false});
        rendered=!!layout.querySelector('math') && layout.querySelectorAll('*').length <= 1500
          && !layout.querySelector('[href],[src],[xlink\\:href],script,iframe,img,svg,style');
      } catch { /* Unsupported/bounded parsing remains readable as exact text. */ }
    }
    if (rendered) {
      figure.dataset.mathPreview='rendered';
      const details=doc.createElement('details'), summary=doc.createElement('summary');
      summary.textContent='查看原始公式（LaTeX）'; details.append(summary,raw);
      figure.append(layout,details);
    } else {
      figure.dataset.mathPreview='raw';
      const label=doc.createElement('p'); label.className='muted'; label.textContent='公式按原始 LaTeX 显示';
      figure.append(label,raw);
    }
    nodes.push(figure);
  }
  target.replaceChildren(...nodes);
}
