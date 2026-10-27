import { createVoice, digitWords, spokenNumber } from './speech.js';

(() => {
  const result = document.querySelector('#result');
  const expression = document.querySelector('#expression');
  const keypad = document.querySelector('.keypad');
  let current = '0';
  let stored = null;
  let operator = null;
  let replaceCurrent = false;
  let justEvaluated = false;
  let waitingForCalculation = false;

  let voiceBusy = false;
  const voice = createVoice({
    onBusy: (busy) => { voiceBusy = busy; render(); },
    onCommands: async (keys) => {
      for (const key of keys) {
        await press(key);
        if (current === 'Error') break;
      }
    },
  });

  const operatorSymbols = { '+': '+', '-': '−', '*': '×', '/': '÷' };

  function render() {
    result.textContent = current;
    keypad.querySelectorAll('button').forEach((button) => {
      button.disabled = waitingForCalculation || voiceBusy;
    });
    voice.setCalculating(waitingForCalculation);
    keypad.querySelectorAll('[data-operator]').forEach((button) => {
      button.classList.toggle('is-selected', button.dataset.operator === operator && !replaceCurrent);
    });
  }

  function format(value) {
    if (!Number.isFinite(value)) return 'Error';
    const rounded = Number.parseFloat(value.toPrecision(12));
    return String(rounded);
  }

  function inputDigit(digit) {
    if (current === 'Error' || replaceCurrent || justEvaluated) {
      current = digit;
      replaceCurrent = false;
      justEvaluated = false;
    } else if (current === '0') {
      current = digit;
    } else if (current.replace('-', '').length < 14) {
      current += digit;
    }
  }

  async function requestCalculation(left, right, operation) {
    const response = await fetch('/api/calculate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ operands: [left, right], operator: operation }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Calculation failed.');
    return data.result;
  }

  async function chooseOperator(nextOperator) {
    const value = Number(current);
    if (!Number.isFinite(value)) return;
    if (operator && !replaceCurrent && stored !== null) {
      waitingForCalculation = true;
      render();
      try {
        stored = await requestCalculation(stored, value, operator);
        current = format(stored);
      } catch (error) {
        current = 'Error';
        expression.textContent = error.message || 'Calculation failed.';
        stored = null;
        operator = null;
        replaceCurrent = true;
        justEvaluated = true;
        return;
      } finally {
        waitingForCalculation = false;
        render();
      }
    } else {
      stored = value;
    }
    operator = nextOperator;
    expression.textContent = `${format(stored)} ${operatorSymbols[operator]}`;
    replaceCurrent = true;
    justEvaluated = false;
  }

  async function equals() {
    if (!operator || stored === null || current === 'Error') return;
    const left = stored;
    const right = Number(current);
    const activeOperator = operator;
    expression.textContent = `${format(left)} ${operatorSymbols[activeOperator]} ${format(right)} =`;
    stored = null;
    operator = null;
    replaceCurrent = true;
    justEvaluated = true;
    waitingForCalculation = true;
    render();
    try {
      current = format(await requestCalculation(left, right, activeOperator));
    } catch (error) {
      current = 'Error';
      expression.textContent = error.message || 'Calculation failed.';
    } finally {
      waitingForCalculation = false;
      render();
    }
  }

  async function applyPercent() {
    if (current === 'Error') return;
    waitingForCalculation = true;
    render();
    try {
      current = format(await requestCalculation(Number(current), 100, '/'));
    } catch (error) {
      current = 'Error';
      expression.textContent = error.message || 'Calculation failed.';
    } finally {
      waitingForCalculation = false;
      render();
    }
  }

  function clear() {
    current = '0';
    stored = null;
    operator = null;
    replaceCurrent = false;
    justEvaluated = false;
    expression.textContent = '';
  }

  async function act(action) {
    if (action === 'clear') clear();
    if (action === 'decimal') {
      if (current === 'Error' || replaceCurrent || justEvaluated) {
        current = '0.';
        replaceCurrent = false;
        justEvaluated = false;
      } else if (!current.includes('.')) current += '.';
    }
    if (action === 'sign' && current !== '0' && current !== 'Error') current = current.startsWith('-') ? current.slice(1) : `-${current}`;
    if (action === 'percent') await applyPercent();
    if (action === 'backspace' && current !== 'Error' && !replaceCurrent && !justEvaluated) {
      current = current.length <= 1 || (current.length === 2 && current.startsWith('-')) ? '0' : current.slice(0, -1);
    }
    if (action === 'equals') await equals();
    render();
  }

  async function press(key) {
    let announcement;
    if (/^\d$/.test(key)) {
      inputDigit(key);
      announcement = digitWords[Number(key)];
    } else if (Object.hasOwn(operatorSymbols, key)) {
      await chooseOperator(key);
      announcement = { '+': 'plus', '-': 'minus', '*': 'times', '/': 'over' }[key];
    } else {
      const actions = { Enter: 'equals', '=': 'equals', '.': 'decimal', Escape: 'clear', Backspace: 'backspace', '%': 'percent', F9: 'sign' };
      await act(actions[key]);
      announcement = { '.': 'point', Escape: 'clear', Backspace: 'backspace', '%': 'percent', F9: 'change sign' }[key];
      if (key === 'Enter' || key === '=') announcement = `is ${spokenNumber(current)}`;
    }
    render();
    voice.speak(current === 'Error' ? expression.textContent : announcement);
  }

  keypad.addEventListener('click', (event) => {
    const button = event.target.closest('button');
    if (!button || waitingForCalculation || voiceBusy) return;
    void voice.unlock().catch(() => {});
    const actionKeys = { clear: 'Escape', decimal: '.', sign: 'F9', percent: '%', backspace: 'Backspace', equals: '=' };
    void press(button.dataset.digit ?? button.dataset.operator ?? actionKeys[button.dataset.action]);
  });

  document.addEventListener('keydown', (event) => {
    if (waitingForCalculation || voiceBusy) return;
    if (/^\d$/.test(event.key) || ['+', '-', '*', '/', 'Enter', '=', '.', 'Escape', 'Backspace', '%', 'F9'].includes(event.key)) {
      if (event.key === 'Enter' && event.target.closest('button')) return;
      event.preventDefault();
      void voice.unlock().catch(() => {});
      void press(event.key);
    }
  });

  render();
})();
