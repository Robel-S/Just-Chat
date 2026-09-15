import _ from 'lodash';

/** Build the demo element rendered by the base Vite entry point. */
function component() {
    const element = document.createElement('div');
    element.innerHTML = _.join(['Hello', 'lodash'], ' ');
    return element;
}
document.body.appendChild(component());
