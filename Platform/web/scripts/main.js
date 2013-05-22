/***********************************************************************
 * Copyright (c) 2013 Ericsson AB
 * 
 * All rights reserved. This program and the accompanying materials
 * are made available under the terms of the Eclipse Public License v1.0
 * which accompanies this distribution, and is available at
 * http://www.eclipse.org/legal/epl-v10.html
 * 
 * Contributors:
 *    Ericsson Research - initial implementation
 *
 ***********************************************************************/

var APP = {};

window.onload = function () {
    APP.weblink = new WebLink(incomingParrotMessage);
    setup_log();
};

/*
 * Functions for reading and writing property values
 *
 * In these functions, 'nodeName' is the URN of a Parrot node, and
 * 'propertyName' is the name of a property that can be accessed
 * using get/set in the Parrot node.
 */

// construct a name of a property that is globally unique
function globalName(nodeName, propertyName) {
    return nodeName + ":::" + propertyName;
}

function requestUpdate(nodeName, propertyName) {
    var request = {
        dest:   nodeName,
        sender: "urn:weblink",
        action: "get",
        key:    propertyName,
    };
    
    APP.weblink.send(request);
}

function setProperty(nodeName, propertyName, propertyValue) {
    var node = document.getElementById(globalName(nodeName, propertyName));
    node.value = propertyValue;
    if (node.className == 'updated1') {
        node.className = 'updated2';
    }
    else {
        node.className = 'updated1';
    }
}

// called when a boolean value is clicked: simply toggle
function editBoolean(nodeName, propertyName) {
    var value = document.getElementById(globalName(nodeName, propertyName)).value;

    if (value.toLowerCase() == "false") {
        value = "true";
    } else {
        value = "false";
    }
    
    var request = {
        dest:   nodeName,
        sender: "urn:weblink",
        action: "set",
        key:    propertyName,
        value:  value
    };
    APP.weblink.send(request);
    
    requestUpdate(nodeName, propertyName);
}

// called when a string value is clicked
function editString(nodeName, propertyName) {
    var value = document.getElementById(globalName(nodeName, propertyName)).value;
    
    var request = {
    dest:   nodeName,
    sender: "urn:weblink",
    action: "set",
    key:    propertyName,
    value:  value
    };
    APP.weblink.send(request);
    
    requestUpdate(nodeName, propertyName);
}

// helper: assign a closure for the editXXX functions above
function setEditor(valueNode, buttonNode, nodeName, propertyName, propertyType) {
    if (propertyType == "boolean") {
        buttonNode.setAttribute('value', 'Toggle');
        buttonNode.onclick = function() { editBoolean(nodeName, propertyName); };
        valueNode.setAttribute('readonly', 'readonly'); // Don't edit booleans, just flip
    }
    else {
        buttonNode.onclick = function() { editString(nodeName, propertyName); };
    }

    valueNode.onkeypress = function(event) {
                               if (event.keyCode == 13) {
                                   buttonNode.onclick();
                               }};
}


/*
 * Logger code
 */

function setup_log()
{
  var div = document.getElementById("log_button");
  div.innerHTML = 'Log filter<br>\
<form id="filter_id">\
<label for="urn">URN:</label>\
<input type="text" name="urn" text="URN">\
<label for="time">Time:</label>\
<input type="text" name="time">\
<label for="cat">Category:</label>\
<input type="text" name="cat">\
<label for="msg">Message:</label>\
<input type="text" name="msg">\
<input type="button" value="Refresh" onclick="generate_log()">\
</form>';
}


function generate_log()
{
    var form = document.getElementById("filter_id");
    var params = [form["urn"].value, form["cat"].value, form["time"].value, form["msg"].value];
    
    var request = {
        dest:"urn:hodcp:core",
        sender:"urn:weblink",
        action:"set",
        key:"log_filter",
        value:params,
    };
    APP.weblink.send(request);
    getLogs();
}
 
function getLogs() {
    var request = {
        dest:"urn:hodcp:core",
        sender:"urn:weblink",
        action:"get",
        key:"log",
    };
    APP.weblink.send(request);
}

function set_logs(logs) {
    // Convert to HTML table
    log = '<table border="1"><th>Timestamp</th><th>Urn</th><th>Category</th><th>Msg</th>';
    for (var i = 0; i < logs.length; i++) {
        d = logs[i];
        log = log + '<tr><td>'+d.timestamp+'</td>'+
                        '<td>'+d.urn+'</td>'+
                        '<td>'+d.category+'</td>'+
                        '<td>'+d.msg+'</td></tr>';

    }
    log = log+'</table>'
    
    document.getElementById("logger").innerHTML = log;
}

/*
 * Parrot callbacks: invoked in response to incoming messages
 */
function incomingParrotMessage(object) {
    if (object.key == "config") {
    setConfiguration(object.value);
    } else if (object.key == "capabilities") {
        setCapabilities(object.sender, object.value);
    } else if (object.key == "log") {
        // FIXME dunno, what should we do with this?
    set_logs(object.value);
    } else {
        setProperty(object.sender, object.key, object.value);
    }
}

function setConfiguration(configData) {
    document.getElementById("description").innerHTML = configData["description"];
    var items = Object.keys(configData["nodes"]);
    // Add backplane to list of nodes
    items.push('urn:backplane');
    for (var i = 0; i < items.length; i++) {
    nodeName = items[i];
        var request = {
            dest: nodeName,
            sender:"urn:weblink",
            action:"get",
            key:"capabilities",
        };
        APP.weblink.send(request);
    }
}

// the DOM node is given the id of the Parrot node it represents
function setCapabilities(nodeName, capabilities) {
    var tableNode = document.getElementById('nodes');
    var simpleName = nodeName.split(':').pop(); // exclude 'urn:hodcp:node:'
    
    // keep the list sorted: look up the first node with a name
    // lexicalically greater than the new one. If there is no such
    // successor -- that is, the new node should be last in the
    // table -- then successor will be null.
    
    // (DISCLAIMER: yes, this makes for quadratic complexity. If we have
    // thousands of nodes, this algorithm should be replaced for something
    // of NlogN complexity.)
    
    var successor = null;
    var rows = tableNode.childNodes;
    for (var i = 0; i < rows.length; i++) {
        var row = rows[i];
        var heading = row.firstChild; // may or may not be a heading
        if (heading && heading.tagName.toLowerCase() == 'th') {
            // now we know it is, in fact, a heading; its only subnode
            // is a text node holding the Parrot node's name
            var parrotNodeName = heading.firstChild.nodeValue;
            if (parrotNodeName > simpleName) {
                successor = row;
                break;
            }
        }
    }
    
    // append a heading for the node, colspan=3
    var rowNode = document.createElement('tr');
    var headingNode = document.createElement('th');
    headingNode.setAttribute('colspan', '3');
    headingNode.appendChild(document.createTextNode(nodeName.split(':').pop()));
    rowNode.appendChild(headingNode);
    
    if (successor) {
        successor.parentNode.insertBefore(rowNode, successor);
    }
    else {
        tableNode.appendChild(rowNode);
    }
    
    // one table row per property
    for (var propertyName in capabilities) {
        var propertyType = capabilities[propertyName]["type"].toLowerCase();
        var previousRow = rowNode;
        
        rowNode = document.createElement('tr');
        
        // property name
        var cellNode = document.createElement('td');
        cellNode.appendChild(document.createTextNode(propertyName));
        rowNode.appendChild(cellNode);
        
        // property value, stored in a text field
        cellNode = document.createElement('td');
        var valueNode = document.createElement('input');
        valueNode.setAttribute('type', 'text');
        valueNode.setAttribute('size', '8'); // should work for most
        valueNode.setAttribute('id', globalName(nodeName, propertyName));
        cellNode.appendChild(valueNode);
        rowNode.appendChild(cellNode);
        
        // edit button
        cellNode = document.createElement('td');
        var buttonNode = document.createElement('input');
        buttonNode.setAttribute('type', 'button');
        buttonNode.setAttribute('value', 'Modify');
        cellNode.appendChild(buttonNode);
        rowNode.appendChild(cellNode);

        setEditor(valueNode, buttonNode, nodeName, propertyName, propertyType);

        // property type
        cellNode = document.createElement('td');
        cellNode.appendChild(document.createTextNode('(' + propertyType + ')'));
        rowNode.appendChild(cellNode);        

        tableNode.insertBefore(rowNode, previousRow.nextSibling)
        
        requestUpdate(nodeName, propertyName);
    }
}
