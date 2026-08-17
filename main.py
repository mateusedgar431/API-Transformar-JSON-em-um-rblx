from flask import Flask, request, jsonify
import requests
import xml.sax.saxutils as saxutils

app = Flask(__name__)

SERVICOS_OFICIAIS = {
    "Workspace": "Workspace",
    "Lighting": "Lighting",
    "ReplicatedFirst": "ReplicatedFirst",
    "ReplicatedStorage": "ReplicatedStorage",
    "ServerScriptService": "ServerScriptService",
    "ServerStorage": "ServerStorage",
    "StarterGui": "StarterGui",
    "StarterPlayer": "StarterPlayer",
    "StarterPack": "StarterPack",
    "Teams": "Teams",
    "SoundService": "SoundService",
    "MaterialService": "MaterialService"
}

MAPA_ENUM_TEXTO_PARA_ID = {
    "Right": 0, "Top": 1, "Back": 2, "Left": 3, "Bottom": 4, "Front": 5,
    "Smooth": 0, "Glue": 1, "Weld": 2, "Studs": 3, "Inlet": 4, 
    "Universal": 5, "Hinge": 6, "Motor": 7, "SteppingMotor": 8,
    "Ball": 0, "Block": 1, "Cylinder": 2, "Wedge": 3,
    "Linear": 0, "In": 0, "Out": 1, "InOut": 2, "Sine": 1, "Quad": 3
}

def normalizar_valor_token(nome_prop, valor):
    if isinstance(valor, dict):
        if "Name" in valor and valor["Name"]:
            valor = valor["Name"]
        elif "Value" in valor:
            valor = valor["Value"]

    if isinstance(valor, str):
        nome_limpo = valor.split(".")[-1]
        if nome_prop == "Material":
            return nome_limpo
        if nome_limpo in MAPA_ENUM_TEXTO_PARA_ID:
            return str(MAPA_ENUM_TEXTO_PARA_ID[nome_limpo])
        if nome_limpo.isdigit():
            return nome_limpo
        return nome_limpo

    if isinstance(valor, int):
        return str(valor)

    return str(valor)

def processar_propriedade_xml(nome_prop, valor, props_dict):
    if valor is None or nome_prop in ["ClassName", "Name", "Parent", "FormFactor"]:
        return ""

    if isinstance(props_dict, dict) and "CFrame" in props_dict and nome_prop in ["Position", "Orientation", "Rotation"]:
        return ""

    # 1. CFRAME
    if nome_prop == "CFrame" and isinstance(valor, list) and len(valor) >= 12:
        return f'''
            <CoordinateFrame name="CFrame">
                <X>{valor[0]}</X><Y>{valor[1]}</Y><Z>{valor[2]}</Z>
                <R00>{valor[3]}</R00><R01>{valor[4]}</R01><R02>{valor[5]}</R02>
                <R10>{valor[6]}</R10><R11>{valor[7]}</R11><R12>{valor[8]}</R12>
                <R20>{valor[9]}</R20><R21>{valor[10]}</R21><R22>{valor[11]}</R22>
            </CoordinateFrame>'''

    # 2. BOOLEANOS
    if isinstance(valor, bool):
        val_str = "true" if valor else "false"
        return f'\n            <bool name="{nome_prop}">{val_str}</bool>'

    # 3. ENUMS / TOKENS
    e_enum = (
        nome_prop in ["Shape", "Font", "PartType", "Face", "NormalId", "Technology", "CameraType"] or
        nome_prop.endswith("Surface") or
        nome_prop.endswith("Type") or 
        nome_prop.endswith("Style") or 
        nome_prop.endswith("Mode") or 
        nome_prop.endswith("Alignment") or 
        nome_prop.endswith("Direction")
    )

    if e_enum or (isinstance(valor, str) and "Enum." in valor):
        val_token = normalizar_valor_token(nome_prop, valor)
        return f'\n            <token name="{nome_prop}">{val_token}</token>'

    # 4. FLOATS
    if isinstance(valor, float):
        return f'\n            <float name="{nome_prop}">{float(valor)}</float>'

    # 5. INTEIROS
    if isinstance(valor, int):
        return f'\n            <int name="{nome_prop}">{valor}</int>'

    # 6. DICIONÁRIOS (Color3 / Vector3 / UDim2)
    if isinstance(valor, dict):
        if "X" in valor and "Y" in valor and isinstance(valor.get("X"), dict):
            x_dict, y_dict = valor.get("X", {}), valor.get("Y", {})
            return f'''
            <UDim2 name="{nome_prop}">
                <XS>{x_dict.get("Scale", 0)}</XS>
                <XO>{x_dict.get("Offset", 0)}</XO>
                <YS>{y_dict.get("Scale", 0)}</YS>
                <YO>{y_dict.get("Offset", 0)}</YO>
            </UDim2>'''

        if "X" in valor and "Y" in valor and "Z" in valor:
            return f'''
            <Vector3 name="{nome_prop}">
                <X>{valor.get("X", 0)}</X><Y>{valor.get("Y", 0)}</Y><Z>{valor.get("Z", 0)}</Z>
            </Vector3>'''

        if "R" in valor and "G" in valor and "B" in valor:
            r = valor["R"] / 255.0 if valor["R"] > 1.0 else valor["R"]
            g = valor["G"] / 255.0 if valor["G"] > 1.0 else valor["G"]
            b = valor["B"] / 255.0 if valor["B"] > 1.0 else valor["B"]
            return f'''
            <Color3 name="{nome_prop}">
                <R>{r}</R>
                <G>{g}</G>
                <B>{b}</B>
            </Color3>'''

    # 7. STRINGS
    if isinstance(valor, str):
        if nome_prop in ["Texture", "Image", "TextureId", "ImageId", "MeshId", "SoundId"] or valor.startswith("rbxassetid://"):
            return f'\n            <Content name="{nome_prop}"><url>{saxutils.escape(valor)}</url></Content>'

        return f'\n            <string name="{nome_prop}">{saxutils.escape(str(valor))}</string>'

    return ""

def processar_objetos_xml(TableData):
    xml_output = ""

    if isinstance(TableData, list):
        for idx, a in enumerate(TableData):
            if isinstance(a, dict):
                props = a.get("Properties", {})
                children = a.get("Children", [])
                script_code = a.get("Script")

                if not isinstance(props, dict):
                    props = {}

                class_name = props.get("ClassName", "Part")
                obj_name = props.get("Name", f"Object_{idx}")

                if script_code and class_name not in ["Script", "LocalScript", "ModuleScript"]:
                    class_name = "Script"

                ref_id = f"RBX_OBJ_{idx}_{abs(hash(obj_name))}"

                xml_output += f'\n<Item class="{class_name}" referent="{ref_id}">'
                xml_output += '\n  <Properties>'
                xml_output += f'\n    <string name="Name">{saxutils.escape(str(obj_name))}</string>'

                if class_name in ["Script", "LocalScript"]:
                    xml_output += '\n    <bool name="Disabled">false</bool>'

                if class_name in ["Part", "WedgePart", "CornerWedgePart", "MeshPart", "SpawnLocation", "BasePart"]:
                    if "Anchored" not in props:
                        props["Anchored"] = True
                    if "CanCollide" not in props:
                        props["CanCollide"] = True

                for nome_prop, val_prop in props.items():
                    xml_output += processar_propriedade_xml(nome_prop, val_prop, props)

                if script_code or class_name in ["Script", "LocalScript", "ModuleScript"]:
                    codigo_str = str(script_code) if script_code is not None else ""
                    codigo_escapado = saxutils.escape(codigo_str)
                    xml_output += f'\n            <ProtectedString name="Source">{codigo_escapado}</ProtectedString>'

                xml_output += '\n  </Properties>'

                if children and isinstance(children, list):
                    xml_output += processar_objetos_xml(children)

                xml_output += '\n</Item>'

    return xml_output

def gerar_script_server(part_data_dict):
    """Gera o script ativado no ServerScriptService com delay para evitar overwrite da engine."""
    servicos_config = {}

    if isinstance(part_data_dict, dict):
        for servico_nome, servico_dados in part_data_dict.items():
            if isinstance(servico_dados, dict) and "Properties" in servico_dados:
                props = servico_dados["Properties"]
                if props:
                    servicos_config[servico_nome] = props

    if not servicos_config:
        return ""

    tabela_luau_linhas = ["local serviceData = {"]
    for s_nome, props in servicos_config.items():
        tabela_luau_linhas.append(f'    ["{s_nome}"] = {{')
        for p_nome, val in props.items():
            if isinstance(val, bool):
                val_str = "true" if val else "false"
                tabela_luau_linhas.append(f'        ["{p_nome}"] = {val_str},')
            elif isinstance(val, (int, float)):
                tabela_luau_linhas.append(f'        ["{p_nome}"] = {val},')
            elif isinstance(val, str):
                tabela_luau_linhas.append(f'        ["{p_nome}"] = "{val}",')
            elif isinstance(val, dict) and "R" in val and "G" in val and "B" in val:
                r, g, b = val["R"], val["G"], val["B"]
                if r <= 1.0 and g <= 1.0 and b <= 1.0:
                    r, g, b = r * 255, g * 255, b * 255
                tabela_luau_linhas.append(f'        ["{p_nome}"] = Color3.fromRGB({int(r)}, {int(g)}, {int(b)}),')
        tabela_luau_linhas.append("    },")
    tabela_luau_linhas.append("}")

    script_luau = "task.wait(0.5)\n" + "\n".join(tabela_luau_linhas) + """

for serviceName, properties in pairs(serviceData) do
    local success, service = pcall(function()
        return game:GetService(serviceName)
    end)
    
    if success and service then
        for propName, propValue in pairs(properties) do
            pcall(function()
                service[propName] = propValue
            end)
        end
    end
end
"""

    codigo_escapado = saxutils.escape(script_luau)

    return f'''
    <Item class="Script" referent="RBX_SERVICE_CONFIGURATOR_SERVER">
        <Properties>
            <string name="Name">__ApplyServiceProperties</string>
            <bool name="Disabled">false</bool>
            <token name="RunContext">0</token>
            <ProtectedString name="Source">{codigo_escapado}</ProtectedString>
        </Properties>
    </Item>'''

def construir_rbxlx_completo(part_data_dict):
    workspace_content = ""
    server_script_service_content = gerar_script_server(part_data_dict)
    outros_servicos = ""

    if isinstance(part_data_dict, dict):
        for servico_nome, servico_dados in part_data_dict.items():
            objetos = []

            if isinstance(servico_dados, dict):
                objetos = servico_dados.get("Objects", [])
            elif isinstance(servico_dados, list):
                objetos = servico_dados

            if servico_nome == "Workspace":
                workspace_content += processar_objetos_xml(objetos)
            elif servico_nome == "ServerScriptService":
                server_script_service_content += processar_objetos_xml(objetos)
            else:
                classe_servico = SERVICOS_OFICIAIS.get(servico_nome, "Folder")
                ref_servico = f"RBX_SERVICE_{servico_nome.upper()}"

                outros_servicos += f'\n<Item class="{classe_servico}" referent="{ref_servico}">'
                outros_servicos += f'\n  <Properties><string name="Name">{servico_nome}</string></Properties>'
                outros_servicos += processar_objetos_xml(objetos)
                outros_servicos += '\n</Item>'

    elif isinstance(part_data_dict, list):
        workspace_content += processar_objetos_xml(part_data_dict)

    rbxlx_str = f'''<roblox xmlns:xmime="http://www.w3.org/2005/05/xmlmime" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://www.roblox.com/roblox.xsd" version="4">
    <External>null</External>
    <External>nil</External>
    <Item class="Workspace" referent="RBX_WORKSPACE_ROOT">
        <Properties>
            <string name="Name">Workspace</string>
            <bool name="FilteringEnabled">true</bool>
        </Properties>
        {workspace_content}
    </Item>
    <Item class="ServerScriptService" referent="RBX_SERVICE_SERVERSCRIPTSERVICE">
        <Properties>
            <string name="Name">ServerScriptService</string>
        </Properties>
        {server_script_service_content}
    </Item>
    {outros_servicos}
</roblox>'''

    return rbxlx_str.encode('utf-8')

@app.route('/publicar', methods=['POST'])
def publicar():
    try:
        dados_json = request.json
        api_key = request.headers.get('x-api-key')
        universe_id = request.headers.get('universe-id')
        place_id = request.headers.get('place-id')

        if not api_key or not universe_id or not place_id:
            return jsonify({"erro": "Headers obrigatorios faltando."}), 400

        conteudo_rbxlx = construir_rbxlx_completo(dados_json)
        url_roblox = f"https://apis.roblox.com/universes/v1/{universe_id}/places/{place_id}/versions?versionType=Published"

        headers_roblox = {
            "x-api-key": api_key,
            "Content-Type": "application/xml",
            "User-Agent": "RobloxOpenCloudClient/1.0"
        }

        resposta = requests.post(url_roblox, headers=headers_roblox, data=conteudo_rbxlx)

        return jsonify({
            "status": resposta.status_code,
            "resposta_roblox": resposta.text
        })

    except Exception as e:
        return jsonify({"erro": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
